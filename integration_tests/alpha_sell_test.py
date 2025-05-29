import asyncio
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import pytest
from bittensor import AsyncSubtensor, AxonInfo
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet

from patrol.validation.predict_alpha_sell import alpha_sell_miner_challenge

@pytest.fixture
def validator_wallet():
    with TemporaryDirectory() as tmp:
        my_wallet = Wallet(name="vali", hotkey="vali", path=tmp)
        my_wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield my_wallet

@pytest.fixture
def mock_subtensor():
    subtensor = AsyncMock(AsyncSubtensor())
    #subtensor = AsyncSubtensor()
    subtensor.get_current_block.return_value = 5551978
    subtensor.get_subnets.return_value = [42]

    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_metagraph.axons = [
        AxonInfo(0, ip="127.0.0.1", port=9000, ip_type=4, hotkey="hk", coldkey="ck")
    ]

    subtensor.metagraph.return_value = mock_metagraph

    return subtensor

@pytest.fixture
def challenge_process(validator_wallet: Wallet, mock_subtensor: AsyncSubtensor):
    process = alpha_sell_miner_challenge.start_process(validator_wallet, mock_subtensor)
    yield process
    process.terminate()
    process.join()

async def test_challenge(challenge_process):
    await asyncio.sleep(10)