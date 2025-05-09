import asyncio
import bittensor as bt
import uuid
import time
from dataclasses import asdict
import json
from datetime import datetime

from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.protocol import HotkeyOwnershipSynapse
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient

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

    target_generator = HotkeyTargetGenerator(substrate_client=client)
    hotkey_addresses = await target_generator.generate_targets(num_targets=256)  

    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    dendrite = bt.dendrite(wallet=wallet_vali)

    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    axon = bt.axon(wallet=wallet_miner, ip="0.0.0.0", port=8000)

    start_time = time.time()

    miner_client = HotkeyOwnershipMinerClient(dendrite=dendrite)

    synapse = HotkeyOwnershipSynapse(target=hotkey_addresses[0])
    response = await miner_client.execute_task(axon.info(), synapse)
    print(response)
    
    # print(f"Final miner scores: {miner_scoring.return_scores()}")

if __name__ == "__main__":

    bt.debug()

    REQUESTS = 10

    asyncio.run(test_miner(REQUESTS))