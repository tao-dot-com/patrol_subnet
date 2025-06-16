import uuid
from tempfile import TemporaryDirectory

import pytest
from aioresponses import aioresponses
from bittensor import Dendrite, AxonInfo
from bittensor_wallet import Wallet

from patrol.validation.error import MinerTaskException
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol_common import WalletIdentifier
from patrol_common.protocol import AlphaSellSynapse

@pytest.fixture
def dendrite_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="alice", hotkey="alice_1", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet


async def test_reject_duplicate_predictions(dendrite_wallet):

    dendrite = Dendrite(dendrite_wallet)
    miner_client = AlphaSellMinerClient(dendrite)
    task_id = str(uuid.uuid4())
    batch_id = str(uuid.uuid4())

    request = AlphaSellSynapse(task_id=task_id, batch_id=batch_id, subnet_uid=10, wallets=[
        WalletIdentifier("alice", "alice_hk")
    ])

    miner = AxonInfo(0, ip="127.0.0.1", port=8000, ip_type=4, hotkey="bob_hk", coldkey="bob")

    with aioresponses() as r:
        response = {
            "task_id": task_id,
            "batch_id": batch_id,
            "subnet_uid": 10,
            "predictions": [
                {"wallet_coldkey_ss58": "alice", "wallet_hotkey_ss58": "alice_1", "amount": 0, "transaction_type": "StakeRemoved"},
                {"wallet_coldkey_ss58": "alice", "wallet_hotkey_ss58": "alice_1", "amount": 0, "transaction_type": "StakeRemoved"},
            ]
        }

        r.post("http://127.0.0.1:8000/AlphaSellSynapse", payload=response)

        error = (await miner_client.execute_tasks(miner, [request]))[0]
        assert isinstance(error, MinerTaskException)

        assert "Duplicate hotkeys found in prediction {'alice_1'}" in str(error)

