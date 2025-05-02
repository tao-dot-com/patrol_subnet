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
from patrol.constants import Constants
from patrol.protocol import PatrolSynapse
from patrol.validation.config import DASHBOARD_BASE_URL, ENABLE_DASHBOARD_SYNDICATION
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.graph_validation.event_checker import EventChecker
from patrol.validation.http.HttpDashboardClient import HttpDashboardClient
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.validator import Validator


class MockMinerScoreRepo:

    def __init__(self):
        self.scores = []

    async def add(self, miner_score):
        self.scores.append(miner_score)

    async def find_latest_overall_scores(self, miner, batch):

        return [1]

    def return_scores(self):
        return self.scores
    
# Custom JSON encoder to handle UUID and datetime objects.
class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


async def query_miners_and_collect_responses(targets, dendrite, axon_info, max_block_number=None):
    """
    Query miners first and collect their responses before validation.
    """
    print(f"\nQuerying miners for {len(targets)} targets...")
    
    responses = []
    
    for target in targets:
        try:
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
            
            responses.append((target, synapse))
            print(f"Received response for target {target[0]} at block {target[1]}")
            
        except Exception as e:
            print(f"Error querying miner for target {target[0]}: {str(e)}")
            responses.append((target, None))
    
    return responses


async def populate_event_store(
    responses, 
    event_fetcher, 
    event_processor, 
    event_repository
):
    """
    Pre-populate events store with events from miner responses.
    """
    print(f"\nExtracting block information from {len(responses)} responses...")
    
    all_block_numbers = set()
    targets_with_responses = []
    
    # Extract exact block numbers from responses
    for target, response in responses:
        if response:
            try:
                # Add the target block number
                all_block_numbers.add(target[1])
                
                # Access all block numbers from the various edges in response
                if hasattr(response, 'subgraph_output'):
                    subgraph = response.subgraph_output
                    
                    if hasattr(subgraph, 'edges'):
                        for edge in subgraph.edges:
                            if hasattr(edge, 'evidence') and hasattr(edge.evidence, 'block_number'):
                                block_num = edge.evidence.block_number
                                all_block_numbers.add(block_num)
                
                targets_with_responses.append((target, response))
            except Exception as e:
                print(f"Error extracting blocks from response for target {target[0]}: {e}")
    
    print(f"Collecting events for {len(all_block_numbers)} unique blocks from miner responses...")
    
    # Fetch and process events for all block numbers
    if all_block_numbers:
        events = await event_fetcher.fetch_all_events(list(all_block_numbers))
        processed_events = await event_processor.process_event_data(events)
        
        # Format events for storing in the database
        db_events = []
        for event in processed_events:
            # Convert to format expected by event_store_repository
            db_event = {
                'coldkey_source': event.get('coldkey_source'),
                'coldkey_destination': event.get('coldkey_destination'),
                'edge_category': event.get('category'),
                'edge_type': event.get('type'),
                'coldkey_owner': event.get('coldkey_owner'),
                'block_number': event.get('evidence', {}).get('block_number'),
                'rao_amount': event.get('evidence', {}).get('rao_amount', 0),
                'destination_net_uid': event.get('evidence', {}).get('destination_net_uid'),
                'source_net_uid': event.get('evidence', {}).get('source_net_uid'),
                'alpha_amount': event.get('evidence', {}).get('alpha_amount', 0),
                'delegate_hotkey_source': event.get('evidence', {}).get('delegate_hotkey_source'),
                'delegate_hotkey_destination': event.get('evidence', {}).get('delegate_hotkey_destination')
            }
            
            db_events.append(db_event)
        
        # Store in repository
        if db_events:
            await event_repository.add_events(db_events)
            print(f"Stored {len(db_events)} events in the event repository for {len(all_block_numbers)} blocks!")
        else:
            print("No valid events to store from the blocks in miner responses")
    else:
        print("No valid block numbers found in miner responses")
    
    return targets_with_responses


async def test_miner(requests):

    bt.debug()

    network_url = "wss://archive.chain.opentensor.ai:443/"

    # Create an instance of SubstrateClient.
    versions = load_versions()
        
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    await client.initialize()

    # Setup an in-memory SQLite database for testing
    DB_URL = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(DB_URL)
    event_repository = DatabaseEventStoreRepository(engine)
    event_checker = EventChecker(engine)

    event_fetcher = EventFetcher(substrate_client=client)
    coldkey_finder = ColdkeyFinder(substrate_client=client)
    event_processor = EventProcessor(coldkey_finder=coldkey_finder)
    target_generator = TargetGenerator(event_fetcher, event_processor)
    
    await create_tables(engine)
    targets = await target_generator.generate_targets(REQUESTS)
    targets.extend(
        [("5CFi7LePvBDSK6RXJ1TyHY1j8ha2WXvypmH4EBqnDjVT7QZ2", 4199740), ("5ECgV72HLnDjT1hX4zP2joFNbajgAyK94oeL9pwAF6JxP46e", 4199740)]
    )
    targets = list(set(targets))

    current_block = await target_generator.get_current_block()
    max_block_number = current_block - 10
    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    dendrite = bt.dendrite(wallet=wallet_vali)

    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    axon = bt.axon(wallet=wallet_miner, ip="0.0.0.0", port=8000)

    miner_scoring_repo = MockMinerScoreRepo()

    miner_validator = Validator(
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
        enable_dashboard_syndication=ENABLE_DASHBOARD_SYNDICATION
    )

    # Prepare event store
    responses = await query_miners_and_collect_responses(targets, dendrite, axon.info(), max_block_number)
    await populate_event_store(
        responses,
        event_fetcher,
        event_processor,
        event_repository
    )

    start_time = time.time()

    tasks = [miner_validator.query_miner(uuid.uuid4(), 1, axon.info(), target, max_block_number=max_block_number) for target in targets]

    await asyncio.gather(*tasks, return_exceptions=True)

    print(f"{requests} made in {time.time() - start_time}")
    scores = miner_scoring_repo.return_scores()

    scores_dict_list = [asdict(score) for score in scores]

    # Save the list of dictionaries to a JSON file using the custom encoder.
    with open("scores.json", "w") as f:
        json.dump(scores_dict_list, f, indent=4, cls=CustomEncoder)

    # print(f"Final miner scores: {miner_scoring.return_scores()}")

if __name__ == "__main__":

    bt.debug()

    REQUESTS = 10

    asyncio.run(test_miner(REQUESTS))