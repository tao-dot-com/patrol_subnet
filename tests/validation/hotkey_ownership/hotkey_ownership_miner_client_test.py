from tempfile import TemporaryDirectory

import pytest
from bittensor import Axon, Dendrite
from bittensor_wallet import Wallet

from patrol.protocol import HotkeyOwnershipSynapse, GraphPayload, Node, Edge, HotkeyOwnershipEvidence
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import MinerTaskException, HotkeyOwnershipMinerClient


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

@pytest.fixture()
def mock_miner(miner_wallet):
    axon = Axon(wallet=miner_wallet, port=8000, external_ip="127.0.0.1").attach(forward_fn=synapse_handler).start()

    yield "127.0.0.1", 8000
    axon.stop()

async def synapse_handler(request: HotkeyOwnershipSynapse):
    request.subgraph_output=GraphPayload(
        nodes=[
            Node("foo", type="wallet", origin="bittensor"),
            Node("bar", type="wallet", origin="bittensor")
        ],
        edges=[Edge("foo", "bar", "hotkey_ownership", "change", HotkeyOwnershipEvidence(
            4567
        ))]
    )
    return request

async def test_challenge_miner(dendrite_wallet, miner_wallet, mock_miner):

    miner_host, miner_port = mock_miner

    dendrite = Dendrite(dendrite_wallet)
    synapse = HotkeyOwnershipSynapse(
        target_hotkey_ss58="5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
    )

    task = HotkeyOwnershipMinerClient(dendrite)

    miner = Axon(port=miner_port, ip=miner_host, wallet=miner_wallet)

    response, response_time = await task.execute_task(miner.info(), synapse)

    assert response_time == pytest.approx(0.2, 1.0)

    assert response.target_hotkey_ss58 == "5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
    assert response.subgraph_output.nodes == [
        Node("foo", type="wallet", origin="bittensor"),
        Node("bar", type="wallet", origin="bittensor")
    ]
    assert response.subgraph_output.edges == [
        Edge("foo", "bar", "hotkey_ownership", "change", HotkeyOwnershipEvidence(4567))
    ]

async def test_challenge_unavailable_miner(dendrite_wallet, miner_wallet):

    dendrite = Dendrite(dendrite_wallet)
    synapse = HotkeyOwnershipSynapse(
        target_hotkey_ss58="5C4hrfjw9DjXZTzV3MwzrrAr9P1MJhSrvWGWqi1eSuyUpnhM"
    )

    task = HotkeyOwnershipMinerClient(dendrite)

    miner = Axon(port=8000, ip="127.0.0.1", wallet=miner_wallet)

    with pytest.raises(MinerTaskException) as ex:
        await task.execute_task(miner.info(), synapse)

    assert "Error: Service unavailable" in str(ex.value)
    assert "status 503" in str(ex.value)