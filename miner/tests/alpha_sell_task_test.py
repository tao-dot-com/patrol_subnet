import asyncio
import multiprocessing
import uuid
from tempfile import TemporaryDirectory
from time import sleep

from bittensor import AsyncSubtensor
import pytest
from bittensor_wallet.bittensor_wallet import Wallet
import bittensor as bt

from patrol_common import PredictionInterval, WalletIdentifier, AlphaSellPrediction, TransactionType
from patrol_common.protocol import AlphaSellSynapse
from patrol_mining.miner import Miner


@pytest.fixture
def miner_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="miner", hotkey="miner", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet


@pytest.fixture
def validator_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="vali", hotkey="vali", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet


@pytest.fixture
def miner_service(miner_wallet):
    async def boot_async():
        async with AsyncSubtensor() as subtensor:
            miner = Miner(
                dev_flag=True,
                wallet_path=miner_wallet.path,
                coldkey=miner_wallet.name,
                hotkey=miner_wallet.hotkey_str,
                port=8000,
                external_ip="127.0.0.1",
                netuid=81,
                subtensor=subtensor,
                min_stake_allowed=30_000,
                network_url="wss://archive.chain.opentensor.ai:443",
                max_future_events=50,
                max_past_events=50,
                batch_size=25
            )

            await miner.run()

    def boot_process():
        asyncio.run(boot_async())

    process = multiprocessing.Process(target=boot_process, daemon=True)
    process.start()
    sleep(2)
    yield process
    process.terminate()
    process.join()


async def test_alpha_sell_task(validator_wallet: Wallet, miner_service: multiprocessing.Process, miner_wallet):
    dendrite = bt.Dendrite(validator_wallet)

    synapse = AlphaSellSynapse(
        task_id=str(uuid.uuid4()),
        batch_id=str(uuid.uuid4()),
        subnet_uid=81,
        prediction_interval=PredictionInterval(5_000_000, 5_000_100),
        wallets=[
            WalletIdentifier("alice", "alice_1"),
            WalletIdentifier("bob", "bob_1"),
        ])

    miner_axon = bt.Axon(miner_wallet, port=8000, ip="0.0.0.0", external_ip="127.0.0.1")
    response: AlphaSellSynapse = await dendrite.call(miner_axon, synapse, timeout=16, deserialize=True)

    assert response.is_success == True
    assert response.batch_id == synapse.batch_id
    assert response.task_id == synapse.task_id
    assert len(response.predictions) == 4
    assert AlphaSellPrediction("alice_1", "alice", TransactionType.STAKE_REMOVED, 0) in response.predictions
    assert AlphaSellPrediction("alice_1", "alice", TransactionType.STAKE_ADDED, 0) in response.predictions
    assert AlphaSellPrediction("bob_1", "bob", TransactionType.STAKE_REMOVED, 0) in response.predictions
    assert AlphaSellPrediction("bob_1", "bob", TransactionType.STAKE_ADDED, 0) in response.predictions
