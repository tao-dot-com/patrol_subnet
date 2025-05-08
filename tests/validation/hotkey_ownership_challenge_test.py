from unittest.mock import AsyncMock, MagicMock

import pytest
from bittensor import AxonInfo

from patrol.protocol import HotkeyOwnershipSynapse, GraphPayload, Node, Edge, HotkeyOwnershipEvidence
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient


async def test_validation_of_valid_graph():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor")
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123, 234, 456)
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, None)

    miner = MagicMock(AxonInfo)

    await challenge.execute_challenge(miner, "abddef12345")

async def test_validation_with_unconnected_node():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
                Node("carol", type="wallet", origin="bittensor")
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123, 234, 456)
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, None)

    miner = MagicMock(AxonInfo)

    with pytest.raises(ValueError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Graph is not fully connected."

async def test_validation_with_unconnected_edges():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123, 234, 456)
                ),
                Edge(
                    coldkey_source="alice", coldkey_destination="carol", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123, 234, 456)
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, None)

    miner = MagicMock(AxonInfo)

    with pytest.raises(ValueError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Edge refers to an absent node."

async def test_validation_with_duplicate_nodes():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("alice", type="wallet", origin="bittensor"),
            ],
            edges=[]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, None)

    miner = MagicMock(AxonInfo)

    with pytest.raises(ValueError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Duplicate node: alice"
