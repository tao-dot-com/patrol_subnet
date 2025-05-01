import asyncio
import bittensor as bt
import uuid
import time
from dataclasses import asdict
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.chain_data.event_collector import create_tables
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.event_processor import EventProcessor
from patrol.validation.config import DASHBOARD_BASE_URL, ENABLE_DASHBOARD_SYNDICATION
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.graph_validation.event_checker import EventChecker
from patrol.validation.http.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.validator import Validator
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions


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



async def populate_event_store(
    targets, 
    event_fetcher, 
    event_processor, 
    event_repository, 
    range_before=100, 
    range_after=100
):
    """
    Pre-populate events store with events from the generated targets.
    """
    print(f"\nCollecting events for {len(targets)} targets...")
    
    all_block_numbers = set()
    
    # Generate block numbers around the target
    for coldkey, target_block in targets:
        start_block = max(target_block - range_before, 1)
        end_block = target_block + range_after
        
        block_numbers = list(range(start_block, end_block + 1))
        all_block_numbers.update(block_numbers)
    
    print(f"Collecting events for {len(all_block_numbers)} blocks...")
    
    # Fetch and process events for all block numbers
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
        
        # Validate that we have required fields
        if db_event['coldkey_source'] and db_event['block_number'] is not None:
            db_events.append(db_event)
    
    # Store in repository
    if db_events:
        await event_repository.add_events(db_events)
        print(f"Stored {len(db_events)} events in the event repository!")
    else:
        print("No valid events to store")
    
    # Return list of target tuples for verification
    valid_target_tuples = []
    for coldkey, block_number in targets:
        # Check if we have events for this coldkey
        coldkey_events = [e for e in db_events if e['coldkey_source'] == coldkey or e['coldkey_destination'] == coldkey]
        if coldkey_events:
            valid_target_tuples.append((coldkey, block_number))
    
    print(f"Found {len(valid_target_tuples)} valid targets with events")
    return valid_target_tuples


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
    valid_target_tuples = await populate_event_store(
        targets, 
        event_fetcher, 
        event_processor, 
        event_repository
    )

    if valid_target_tuples:
        # Select up to 'requests' number of unique targets
        targets = list(set(valid_target_tuples))[:requests]
        print(f"Using {len(targets)} targets from subgraph data")

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