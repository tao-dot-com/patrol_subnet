import asyncio
import json
import time
import uuid
from dataclasses import asdict
from datetime import datetime

import aiohttp
import bittensor as bt
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.event_collector import create_tables
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_processor import EventProcessor
from patrol.chain_data.runtime_groupings import load_versions
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.constants import Constants, TaskType
from patrol.protocol import PatrolSynapse
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.chain.runtime_versions import RuntimeVersions
from patrol.validation.coldkey_target_generation import TargetGenerator
from patrol.validation.config import DASHBOARD_BASE_URL, ENABLE_DASHBOARD_SYNDICATION
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.graph_validation.event_checker import EventChecker
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, HotkeyOwnershipValidator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository

from patrol.validation.validator import TaskSelector, Validator
from sqlalchemy import text

class MockMinerScoreRepo:
    def __init__(self):
        self.scores = []

    async def add(self, miner_score):
        self.scores.append(miner_score)

    # The real MinerScoreRepository's method signature has 3 parameters
    # Like: (self, miner_identifier, batch_size, exclude_batch_id=None)
    async def find_latest_overall_scores(self, miner, batch, exclude_batch_id=None):
        return [1]

    def return_scores(self):
        return self.scores
    
# Enhanced CustomEncoder to handle TaskType enums
class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, TaskType):
            return o.name  # Convert enum to string name
        try:
            # Try to convert to dict for any other complex types
            return o.__dict__
        except (AttributeError, TypeError):
            return super().default(o)


async def query_miners_and_collect_responses(targets, dendrite, axon_info, max_block_number=None, request_sleep=0.1):
    """
    Query miners first and collect their responses before validation.
    """
    print(f"\nQuerying miners for {len(targets)} targets...")
    
    responses = []
    
    for i, target in enumerate(targets):
        try:
            # Start timing
            query_start = time.time()
            
            synapse = PatrolSynapse(target=target[0], target_block_number=target[1], max_block_number=max_block_number)
            processed_synapse = dendrite.preprocess_synapse_for_request(axon_info, synapse)
            url = dendrite._get_endpoint_url(axon_info, "PatrolSynapse")
            
            # Simple context manager to ensure proper cleanup
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url,
                        headers=processed_synapse.to_headers(),
                        json=processed_synapse.model_dump(),
                        timeout=Constants.MAX_RESPONSE_TIME
                ) as response:
                    if response.ok:
                        json_response = await response.json()
                    else:
                        raise Exception(f"Bad response status {response.status}")
            
            synapse.subgraph_output = json_response.get('subgraph_output')
            
            # Calculate response time
            query_time = time.time() - query_start
            
            # Store tuple with target, response and the actual response time
            responses.append((target, synapse, query_time))
            print(f"Received response for target {target[0]} at block {target[1]} in {query_time:.3f}s")
            
            # Add sleep between requests (except for the last one)
            if i < len(targets) - 1 and request_sleep > 0:
                print(f"Sleeping for {request_sleep}s before next query...")
                await asyncio.sleep(request_sleep)
                
        except Exception as e:
            print(f"Error querying miner for target {target[0]}: {str(e)}")
            responses.append((target, None, None))
    
    return responses

async def generate_targets_from_db(engine, num_targets, max_block=None):
    """
    Generate targets (coldkey, block_number) from the PostgreSQL database.
    More inclusive to find all coldkeys, including those with only self-transfers.
    """
    async with engine.connect() as conn:
        # Build WHERE clause with max_block if provided
        block_condition = ""
        if max_block is not None:
            block_condition = f"AND block_number <= {max_block}"
            
        # More inclusive query that finds all coldkeys regardless of connection type
        query = text(f"""
            SELECT coldkey, block_number FROM (
                -- Get all coldkeys that appear as source
                SELECT DISTINCT coldkey_source as coldkey, block_number 
                FROM event_store 
                WHERE coldkey_source IS NOT NULL
                {block_condition}
                -- UNION
                -- -- Get all coldkeys that appear as destination
                -- SELECT DISTINCT coldkey_destination as coldkey, block_number 
                -- FROM event_store 
                -- WHERE coldkey_destination IS NOT NULL
                -- {block_condition}
            ) combined
            ORDER BY RANDOM() 
            LIMIT :limit
        """)
        
        result = await conn.execute(query, {"limit": num_targets})
        targets = [(row.coldkey, row.block_number) for row in result]
    
    return targets

async def test_miner(requests, request_sleep=1):

    bt.debug()

    # network_url = "ws://5.9.118.137:9944"
    # network_url = "ws://5.161.188.96:9944"

    # Create an instance of SubstrateClient.
    # versions = load_versions()

    # Filter runtime versions to a smaller subset for testing
    # This reduces initialization time and resource usage
    # keys_to_keep = {"149", "152", "153"}
    # versions = {k: versions[k] for k in keys_to_keep if k in versions}
    
    # # Log the versions being used
    # print(f"Using runtime versions: {list(versions.keys())}")
        
    # client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    # await client.initialize()

    # Setup an in-memory SQLite database for testing
    DB_URL = "postgresql+asyncpg://patrol:password@localhost:5432/patrol"
    engine = create_async_engine(DB_URL)
    event_repository = DatabaseEventStoreRepository(engine)
    event_checker = EventChecker(engine)

    max_block_number = 5602116
    event_fetcher = None
    coldkey_finder = None
    event_processor = EventProcessor(coldkey_finder=coldkey_finder)
    
    targets = await generate_targets_from_db(engine=engine, 
                                             num_targets=REQUESTS,
                                             max_block=max_block_number)
    targets = list(set(targets))

    # current_block = await target_generator.get_current_block()
    # max_block_number = current_block - 10
    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    dendrite = bt.dendrite(wallet=wallet_vali)

    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    # axon = bt.axon(wallet=wallet_miner, ip="0.0.0.0", port=8000)
    # dev
    external_ip = "13.248.136.93"
    axon = bt.axon(wallet=wallet_miner, external_ip=external_ip, port=5081)

    miner_scoring_repo = MockMinerScoreRepo()

    
    # Create TaskSelector - configured to only select PatrolSynapse tasks
    task_selector = TaskSelector(weightings={
        TaskType.COLDKEY_SEARCH: 1.0,     # PatrolSynapse for graph validation
        TaskType.HOTKEY_OWNERSHIP: 0.0      # Disable HotkeyOwnershipSynapse tasks
    })

    # Create the Validator with all required parameters
    miner_validator = Validator(
        chain_reader=None,
        validation_mechanism=BittensorValidationMechanism(event_checker),
        target_generator=TargetGenerator(event_fetcher, coldkey_finder),
        scoring_mechanism=MinerScoring(miner_score_repository=miner_scoring_repo),
        miner_score_repository=miner_scoring_repo,
        dendrite=dendrite,
        metagraph=None,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=None,
        enable_weight_setting=False,
        dashboard_client=HttpDashboardClient(wallet_vali, DASHBOARD_BASE_URL),
        enable_dashboard_syndication=ENABLE_DASHBOARD_SYNDICATION,
        task_selector=task_selector,
        hotkey_target_generator=None,
        hotkey_ownership_challenge=None
    )

    # Instead of calling populate_event_store, you could:
    responses = await query_miners_and_collect_responses(
        targets, 
        dendrite, 
        axon.info(), 
        max_block_number, 
        request_sleep=request_sleep
    )

    # Create a dictionary to store the actual response times
    target_to_time = {}
    for target, response, query_time in responses:
        if query_time is not None:
            target_to_time[target] = query_time

    # Skip populate_event_store() call
    start_time = time.time()
    tasks = []
    task_to_target = {}  # Map to track which task corresponds to which target

    validation_semaphore = asyncio.Semaphore(REQUESTS)

    async def validate_with_semaphore(task_uuid, uid, axon_info, target, max_block_number):
        async with validation_semaphore:
            # Store the UUID in the validator's parameters directly
            result = await miner_validator.query_miner(
                task_uuid, uid, axon_info, target, max_block_number
            )
            # Make sure we track which target was used with this UUID
            return (result, target)

    # First, replace the validation loop with this version that collects results
    results = []
    for target, response, _ in responses:
        if response:
            task_uuid = uuid.uuid4()
            task = asyncio.create_task(validate_with_semaphore(
                task_uuid, 1, axon.info(), target, max_block_number
            ))
            tasks.append(task)
            # Store the target for this task
            task_to_target[task_uuid] = target

    # Wait for all tasks to complete and collect results
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    print(f"{requests} validated in {time.time() - start_time}")
    scores = miner_scoring_repo.return_scores()

    # Match scores with targets using timestamps and other information
    # Sort both by timestamps
    scores.sort(key=lambda s: s.created_at)
    responses_with_time = [(t, r, tm) for t, r, tm in responses if r is not None]
    responses_with_time.sort(key=lambda x: x[2])  # Sort by query_time

    # Create direct mapping if we have the same number of responses as scores
    scores_dict_list = []
    for i, score in enumerate(scores):
        score_dict = asdict(score)
        if i < len(responses_with_time):
            target, response, query_time = responses_with_time[i]
            score_dict['target_coldkey'] = target[0]
            score_dict['target_block'] = target[1]
            score_dict['actual_response_time'] = query_time
            score_dict['response_time_with_sleep'] = score.response_time_seconds
        scores_dict_list.append(score_dict)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"scores_{timestamp}.json"
    # Save the list of dictionaries to a JSON file using the custom encoder
    with open(filename, "w") as f:
        json.dump(scores_dict_list, f, indent=4, cls=CustomEncoder)

    print(f"Scores saved to {filename}")

if __name__ == "__main__":

    bt.debug()

    REQUESTS = 20

    asyncio.run(test_miner(REQUESTS))

