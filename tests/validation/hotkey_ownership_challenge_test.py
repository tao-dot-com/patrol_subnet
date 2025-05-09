from unittest.mock import AsyncMock, MagicMock

import pytest
from bittensor import AxonInfo

from patrol.protocol import HotkeyOwnershipSynapse, GraphPayload, Node, Edge, HotkeyOwnershipEvidence
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient


async def test_validation_of_valid_graph():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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
    chain_reader.get_hotkey_owner = AsyncMock(
        side_effect=lambda hk, bn: "alice" if bn < 123 else "bob"
    )

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    await challenge.execute_challenge(miner, "abddef12345")

async def test_validation_with_unconnected_node():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Graph is not fully connected"

async def test_validation_with_unconnected_edges():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == 'Edge destination [carol] is not a node'

async def test_validation_with_duplicate_nodes():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("alice", type="wallet", origin="bittensor"),
            ],
            edges=[]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Duplicate node [alice]"

async def test_validation_with_empty_nodes():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=[],
            edges=[]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Zero nodes"

async def test_validation_with_absent_nodes():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=GraphPayload(
            nodes=None,
            edges=[]
        ))

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Zero nodes"

async def test_validation_with_absent_subgraph():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        hotkey_ss58="abcdef", subgraph_output=None
    )

    miner_client.execute_task.return_value = valid_response

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Missing graph"


async def test_validation_with_incorrect_previous_owner():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response
    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "carol" if bn < 123 else "bob")

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Expected hotkey_owner [alice]; actual [carol] for block [122]"

async def test_validation_with_incorrect_new_owner():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response
    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "alice" if bn < 123 else "carol")

    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Expected hotkey_owner [bob]; actual [carol] for block [124]"

async def test_validation_with_duplicate_edge():

    miner_client = AsyncMock(HotkeyOwnershipMinerClient)
    chain_reader = AsyncMock(ChainReader)

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
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123, 234, 456)
                )
            ]
        ))

    miner_client.execute_task.return_value = valid_response
    challenge = HotkeyOwnershipChallenge(miner_client, chain_reader)

    miner = MagicMock(AxonInfo)

    with pytest.raises(AssertionError) as ex:
        await challenge.execute_challenge(miner, "abddef12345")

    assert str(ex.value) == "Duplicate edge (from=alice, to=bob, block=123)"

