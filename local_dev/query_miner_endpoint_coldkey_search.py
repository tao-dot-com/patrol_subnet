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
from patrol.validation.coldkey_target_generation import TargetGenerator
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

async def test_miner(requests):

    bt.debug()

    network_url = "wss://archive.chain.opentensor.ai:443/"
        
    # Create an instance of SubstrateClient.
    versions = load_versions()
        
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    await client.initialize()

    event_fetcher = EventFetcher(substrate_client=client)
    coldkey_finder = ColdkeyFinder(substrate_client=client)
    event_processor = EventProcessor(coldkey_finder=coldkey_finder)

    target_generator = TargetGenerator(event_fetcher, event_processor)

    targets = await target_generator.generate_targets(REQUESTS)
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
        validation_mechanism=BittensorValidationMechanism(event_fetcher, event_processor),
        target_generator=TargetGenerator(event_fetcher, coldkey_finder),
        scoring_mechanism=MinerScoring(miner_score_repository=miner_scoring_repo),
        miner_score_repository=miner_scoring_repo,
        dendrite=dendrite,
        metagraph=None,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=None,
        enable_weight_setting=False
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