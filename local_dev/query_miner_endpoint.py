import asyncio
import bittensor as bt
import uuid
import time
from dataclasses import asdict
import json
from datetime import datetime

from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.event_processor import EventProcessor
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.validator import Validator
from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK

class MockMinerScoreRepo:

    def __init__(self):
        self.scores = []

    async def add(self, miner_score):
        self.scores.append(miner_score)

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

async def test_miner(requests):

    bt.debug()

    network_url = "wss://archive.chain.opentensor.ai:443/"
        
    # Create an instance of SubstrateClient.
    client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=30, max_retries=3)
    
    # Initialize substrate connections for all groups.
    await client.initialize_connections()

    event_fetcher = EventFetcher(substrate_client=client)
    coldkey_finder = ColdkeyFinder(substrate_client=client)
    event_processor = EventProcessor(coldkey_finder=coldkey_finder)

    target_generator = TargetGenerator(event_fetcher, event_processor)

    targets = await target_generator.generate_targets(REQUESTS)

    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    dendrite = bt.dendrite(wallet=wallet_vali)

    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    axon = bt.axon(wallet=wallet_miner, ip="0.0.0.0", port=8000)

    miner_scoring = MockMinerScoreRepo()

    miner_validator = Validator(
        validation_mechanism=BittensorValidationMechanism(event_fetcher, event_processor),
        target_generator=TargetGenerator(event_fetcher, coldkey_finder),
        scoring_mechanism=MinerScoring(),
        miner_score_repository=miner_scoring,
        dendrite=dendrite,
        metagraph=None,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=None,
        enable_weight_setting=False
    )

    start_time = time.time()

    tasks = [miner_validator.query_miner(uuid.uuid4(), 1, axon.info(), target) for target in targets]

    await asyncio.gather(*tasks)

    print(f"{requests} made in {time.time() - start_time}")
    scores = miner_scoring.return_scores()

    scores_dict_list = [asdict(score) for score in scores]

    # Save the list of dictionaries to a JSON file using the custom encoder.
    with open("scores.json", "w") as f:
        json.dump(scores_dict_list, f, indent=4, cls=CustomEncoder)

    # print(f"Final miner scores: {miner_scoring.return_scores()}")

if __name__ == "__main__":

    bt.debug()

    REQUESTS = 10

    asyncio.run(test_miner(REQUESTS))