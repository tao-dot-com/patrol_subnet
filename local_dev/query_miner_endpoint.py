import asyncio
import bittensor as bt
import uuid

from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.validator import Validator

class MockMinerScoreRepo:

    async def add(self, miner_score):
        pass


async def test_miner():

    bt.debug()

    event_fetcher = EventFetcher()
    await event_fetcher.initialize_substrate_connections()

    coldkey_finder = ColdkeyFinder()
    await coldkey_finder.initialize_substrate_connection()


    target = ("5EPdHVcvKSMULhEdkfxtFohWrZbFQtFqwXherScM7B9F6DUD", 5163655)

    wallet_2 = bt.wallet(name="miners", hotkey="miner_1")
    dendrite = bt.dendrite(wallet=wallet_2)

    wallet = bt.wallet(name="miners", hotkey="miner_1")
    axon = bt.axon(wallet=wallet, ip="0.0.0.0", port=8000)

    miner_validator = Validator(
        validation_mechanism=BittensorValidationMechanism(event_fetcher, coldkey_finder),
        target_generator=TargetGenerator(event_fetcher, coldkey_finder),
        scoring_mechanism=MinerScoring(),
        miner_score_repository=MockMinerScoreRepo(),
        dendrite=dendrite,
        metagraph=None,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=None
    )

    await miner_validator.query_miner(uuid.uuid4(), 1, axon.info(), target)

if __name__ == "__main__":

    bt.debug()

    asyncio.run(test_miner())