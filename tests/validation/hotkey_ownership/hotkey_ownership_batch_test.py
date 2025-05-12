from unittest.mock import AsyncMock, call

import numpy
from bittensor import AxonInfo, AsyncSubtensor
from bittensor.core.metagraph import AsyncMetagraph

from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_batch import HotkeyOwnershipBatch
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, Miner
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator


async def test_ownership_batch_challenges_miners():

    # subtensor = AsyncSubtensor("finney")
    # await subtensor.initialize()
    # real_metagraph = await subtensor.metagraph(81)

    challenge = AsyncMock(HotkeyOwnershipChallenge)
    target_generator = AsyncMock(HotkeyTargetGenerator)
    target_generator.generate_targets = AsyncMock(return_value=["bob", "alice"])
    chain_reader = AsyncMock(ChainReader)
    chain_reader.get_current_block = AsyncMock(return_value=5_000_000)

    metagraph = AsyncMock(AsyncMetagraph)

    axons = [
        AxonInfo(0, ip="192.168.1.1", port=8080, ip_type=4, coldkey="", hotkey=""),
        AxonInfo(0, ip="0.0.0.0", port=0, ip_type=4, coldkey="", hotkey=""),
        AxonInfo(0, ip="192.168.1.2", port=8080, ip_type=4, coldkey="", hotkey=""),
    ]

    metagraph.axons = axons
    metagraph.uids = numpy.array([0, 1, 2])

    batch = HotkeyOwnershipBatch(challenge, target_generator, metagraph, chain_reader)
    batch_id = await batch.challenge_miners()

    assert len(challenge.execute_challenge.mock_calls) == 2
    challenge.execute_challenge.assert_has_calls([
        call(Miner(axons[0], 0), "alice", batch_id, 4_999_990),
        call(Miner(axons[2], 2), "bob", batch_id, 4_999_990),
    ])