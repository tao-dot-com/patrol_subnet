from unittest.mock import AsyncMock

import pytest

from patrol.protocol import HotkeyOwnershipSynapse, GraphPayload, Node, Edge, HotkeyOwnershipEvidence
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipValidator, ValidationException


async def test_validation_of_valid_graph():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor")
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        ))

    chain_reader.get_hotkey_owner = AsyncMock(
        side_effect=lambda hk, bn: "alice" if bn < 123 else "bob"
    )

    validator = HotkeyOwnershipValidator(chain_reader)

    await validator.validate(valid_response, "abddef12345")


async def test_validation_with_unconnected_node():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
                Node("carol", type="wallet", origin="bittensor")
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Graph is not fully connected"

async def test_validation_with_unconnected_edges():
    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                ),
                Edge(
                    coldkey_source="alice", coldkey_destination="carol", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == 'Edge destination [carol] is not a node'

async def test_validation_with_duplicate_nodes():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("alice", type="wallet", origin="bittensor"),
            ],
            edges=[]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Duplicate node [alice]"

async def test_validation_with_empty_nodes():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[],
            edges=[]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Zero nodes"

async def test_validation_with_absent_nodes():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=None,
            edges=[]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Zero nodes"

async def test_validation_with_absent_subgraph():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=None
    )

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Missing graph"


async def test_validation_with_incorrect_previous_owner():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        ))

    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "carol" if bn < 123 else "bob")

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Expected hotkey_owner [alice]; actual [carol] for block [122]"

async def test_validation_with_incorrect_new_owner():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
                Node("carol", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                ),
                Edge(
                    coldkey_source="alice", coldkey_destination="carol", category="", type="",
                    evidence=HotkeyOwnershipEvidence(124)
                )
            ]
        ))

    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "alice" if bn < 123 else "carol")

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Expected hotkey_owner [bob]; actual [carol] for block [124]"

async def test_validation_with_incorrect_final_owner():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
                Node("carol", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                ),
                Edge(
                    coldkey_source="bob", coldkey_destination="carol", category="", type="",
                    evidence=HotkeyOwnershipEvidence(124)
                )
            ]
        ))

    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "alice" if bn < 123 else "bob")

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")
    # Actually caught by a different error
    assert str(ex.value) == "Expected hotkey_owner [carol]; actual [bob] for block [125]"

async def test_validation_with_duplicate_edge():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
                Node("bob", type="wallet", origin="bittensor"),
            ],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                ),
                Edge(
                    coldkey_source="alice", coldkey_destination="bob", category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        ))

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Duplicate edge (from=alice, to=bob, block=123)"

async def test_validation_with_no_changes_of_ownership_since_lowest_block_in_range():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
            ],
            edges=[]
        ))
    
    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "alice" if bn < 201 else "alice")

    validator = HotkeyOwnershipValidator(chain_reader)

    await validator.validate(valid_response, "abcdef")

async def test_validation_target_hotkey_not_linked_to_graph():

    chain_reader = AsyncMock(ChainReader)

    valid_response = HotkeyOwnershipSynapse(
        target_hotkey_ss58="abcdef", max_block_number=200, subgraph_output=GraphPayload(
            nodes=[
                Node("alice", type="wallet", origin="bittensor"),
            ],
            edges=[]
        ))
    
    chain_reader.get_hotkey_owner = AsyncMock(side_effect=lambda hk, bn: "bob" if bn < 201 else "carol")

    validator = HotkeyOwnershipValidator(chain_reader)

    with pytest.raises(ValidationException) as ex:
        await validator.validate(valid_response, "abddef12345")

    assert str(ex.value) == "Start owner [carol] is not in the graph"

