import asyncio
import bittensor as bt
import uuid
import json
from datetime import datetime
from collections import namedtuple
from patrol_mining.chain_data.substrate_client import SubstrateClient
from patrol_mining.chain_data.runtime_groupings import load_versions
from patrol.validation.chain.chain_reader import ChainReader

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, HotkeyOwnershipValidator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from async_substrate_interface import AsyncSubstrateInterface

class MockMinerScoreRepo:

    def __init__(self):
        self.scores = []

    async def add(self, miner_score):
        self.scores.append(miner_score)

    async def find_latest_overall_scores(self, miner, batch, limit=None):
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
    
    async_substrate_interface = AsyncSubstrateInterface(network_url)

    chain_reader = ChainReader(async_substrate_interface)

    target_generator = HotkeyTargetGenerator(async_substrate_interface)
    hotkey_addresses = await target_generator.generate_targets(num_targets=10, max_block_number=5551978)  

    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    dendrite = bt.dendrite(wallet=wallet_vali)

    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    axon = bt.axon(wallet=wallet_miner, ip="0.0.0.0", port=8000)

    Miner = namedtuple("Miner", ["axon_info", "uid"])

    miner = Miner(axon_info=axon.info(), uid=1)

    miner_client = HotkeyOwnershipMinerClient(dendrite=dendrite)
    validator = HotkeyOwnershipValidator(chain_reader)
    score_repository = MockMinerScoreRepo()
    ownership_challenge = HotkeyOwnershipChallenge(miner_client=miner_client, scoring=HotkeyOwnershipScoring(), validator=validator, score_repository=score_repository, dashboard_client=None)

    await ownership_challenge.execute_challenge(miner, hotkey_addresses[0], uuid.uuid4(), max_block_number=5551978)
    
    # print(f"Final miner scores: {miner_scoring.return_scores()}")

if __name__ == "__main__":

    bt.debug()

    REQUESTS = 10

    asyncio.run(test_miner(REQUESTS))