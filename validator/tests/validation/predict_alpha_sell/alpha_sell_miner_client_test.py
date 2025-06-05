import asyncio
import time
import uuid
from tempfile import TemporaryDirectory

import pytest
from bittensor import Axon, Dendrite
from bittensor_wallet import Wallet

from patrol.validation.error import MinerTaskException
from patrol.validation.predict_alpha_sell import TransactionType, WalletIdentifier
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse, AlphaSellPrediction, PredictionInterval


@pytest.fixture
def dendrite_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="vali", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

@pytest.fixture
def miner_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="miner", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

async def synapse_handler(request: AlphaSellSynapse):
    await asyncio.sleep(0.2)
    request.predictions=[
        AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
        AlphaSellPrediction("bob", "b",  TransactionType.STAKE_REMOVED, 15)
    ]
    return request


@pytest.fixture()
def mock_miner(miner_wallet):
    axon = Axon(wallet=miner_wallet, port=8000, external_ip="127.0.0.1").attach(forward_fn=synapse_handler).start()

    yield "127.0.0.1", 8000
    axon.stop()
    time.sleep(0.1)


async def test_challenge_miner(dendrite_wallet, miner_wallet, mock_miner):

    miner_host, miner_port = mock_miner

    batch_id = uuid.uuid4()
    task_id = uuid.uuid4()

    dendrite = Dendrite(dendrite_wallet)
    synapse = AlphaSellSynapse(
        batch_id=str(batch_id),
        task_id=str(task_id),
        subnet_uid=42,
        wallets=[WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob")],
        prediction_interval=PredictionInterval(5000000, 50007200),
    )

    task = AlphaSellMinerClient(dendrite)

    miner = Axon(port=miner_port, ip=miner_host, external_ip=miner_host, wallet=miner_wallet)

    responses = await task.execute_tasks(miner.info(), [synapse])

    assert responses[0][0] == batch_id
    assert responses[0][1] == task_id


async def test_challenge_unavailable_miner(dendrite_wallet, miner_wallet, mock_miner):

    dendrite = Dendrite(dendrite_wallet)
    synapse = AlphaSellSynapse(
        batch_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        subnet_uid=42,
        prediction_interval=PredictionInterval(5000000, 50007200),
        wallets=[WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob")],
    )

    task = AlphaSellMinerClient(dendrite)

    miner = Axon(port=8009, ip="127.0.0.1", external_ip="127.0.0.1", wallet=miner_wallet)

    responses = await task.execute_tasks(miner.info(), [synapse])

    response = responses[0]
    assert isinstance(response, MinerTaskException)
    assert "Connect call failed" in str(response)

async def test_challenge_miner_with_timeout(dendrite_wallet, miner_wallet, mock_miner):

    miner_ip, miner_port = mock_miner

    dendrite = Dendrite(dendrite_wallet)
    synapse = AlphaSellSynapse(
        batch_id=str(uuid.uuid4()),
        task_id=str(uuid.uuid4()),
        subnet_uid=42,
        prediction_interval=PredictionInterval(5000000, 50007200),
        wallets=[WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob")],
    )

    task = AlphaSellMinerClient(dendrite, 0.01)

    miner = Axon(port=miner_port, ip=miner_ip, external_ip=miner_ip, wallet=miner_wallet)

    responses = await task.execute_tasks(miner.info(), [synapse])
    assert isinstance(responses[0], MinerTaskException)
    assert "Timeout" in str(responses[0])
