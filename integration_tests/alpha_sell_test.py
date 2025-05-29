import asyncio
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import bittensor as bt
import pytest
from bittensor import AsyncSubtensor, AxonInfo
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet

from patrol.validation.predict_alpha_sell import alpha_sell_miner_challenge, AlphaSellPrediction, TransactionType
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse

DB_URL = "postgresql+asyncpg://patrol:password@localhost:5432/patrol"

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


    def mock_metagraph_fn(net_uid: int):
        if net_uid == 81:
            mock_metagraph = AsyncMock(AsyncMetagraph)
            mock_metagraph.axons = [
                AxonInfo(0, ip="127.0.0.1", port=9000, ip_type=4, hotkey="hk", coldkey="ck")
            ]
            return mock_metagraph
        else:
            mock_metagraph = AsyncMock(AsyncMetagraph)
            mock_metagraph.hotkeys = ["alice", "bob"]
            return mock_metagraph

    subtensor.metagraph = AsyncMock(side_effect=mock_metagraph_fn)

    return subtensor

async def alpha_sell_synapse_handler(synapse: AlphaSellSynapse):
    synapse.predictions = [
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 25.0),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 5.0),
    ]
    return synapse


@pytest.fixture
def mock_miner():
    with TemporaryDirectory() as tmp:
        miner_wallet = Wallet(name="miner", hotkey="miner", path=tmp)
        miner_wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)

        def verify(synapse: AlphaSellSynapse) -> None:
            pass

        miner = bt.Axon(miner_wallet, port=9000, ip="0.0.0.0", external_ip="127.0.0.1")
        miner.attach(forward_fn=alpha_sell_synapse_handler, verify_fn=verify)
        miner.start()

        yield miner
        miner.stop()

@pytest.fixture
def challenge_process(mock_miner, validator_wallet: Wallet, mock_subtensor: AsyncSubtensor):
    process = alpha_sell_miner_challenge.start_process(validator_wallet, mock_subtensor, DB_URL)
    yield process
    process.terminate()
    process.join()

async def test_challenge(challenge_process):
    await asyncio.sleep(100)