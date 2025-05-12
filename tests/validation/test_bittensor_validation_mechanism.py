import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.protocol import Node, Edge, TransferEvidence, GraphPayload
from patrol.validation.miner_scoring import ValidationResult
from patrol.validation.graph_validation.errors import PayloadValidationError, SingleNodeResponse

@pytest.fixture
def validator():
    # By default we don’t need an event_checker for most helper tests
    return BittensorValidationMechanism(event_checker=None)

@pytest.mark.asyncio
async def test_validate_payload_empty(validator):
    # payload=None should short‐circuit before using event_checker
    result = await validator.validate_payload(uid=1, payload=None)
    assert not result.validated
    assert "Empty/Null" in result.message

@pytest.mark.asyncio
async def test_validate_payload_single_node(validator):
    payload = {
        "nodes": [{"id": "a", "type": "neuron", "origin": "user"}],
        "edges": []
    }
    # only one node → early return
    result = await validator.validate_payload(uid=1, payload=payload, target="a")
    assert not result.validated
    assert "Only single node" in result.message

@pytest.mark.asyncio
async def test_validate_payload_valid(validator):
    # two nodes + one edge → validated
    payload = {
        "nodes": [
            {"id": "a", "type": "neuron", "origin": "user"},
            {"id": "b", "type": "neuron", "origin": "user"},
        ],
        "edges": [
            {
                "coldkey_source": "a",
                "coldkey_destination": "b",
                "category": "balance",
                "type": "transfer",
                "evidence": {
                    "rao_amount": 100,
                    "block_number": 5000000
                }
            }
        ]
    }

    class MockEventChecker:
        async def check_events_by_hash(self, event_data_list):
            return event_data_list

    # swap in our checker
    validator.event_checker = MockEventChecker()

    result = await validator.validate_payload(
        uid=1,
        payload=payload,
        target="a",
        max_block_number=5000001
    )
    assert result.validated
    assert result.volume == 3  # 2 nodes + 1 edge

def test_parse_graph_payload_duplicate_nodes(validator):
    payload = {
        "nodes": [
            {"id": "a", "type": "neuron", "origin": "user"},
            {"id": "a", "type": "neuron", "origin": "user"}
        ],
        "edges": []
    }
    with pytest.raises(PayloadValidationError, match="Duplicate node"):
        validator._parse_graph_payload(payload)

def test_parse_graph_payload_duplicate_edges(validator):
    edge = {
        "coldkey_source": "a",
        "coldkey_destination": "b",
        "category": "balance",
        "type": "transfer",
        "evidence": {"rao_amount": 10, "block_number": 1000}
    }
    payload = {
        "nodes": [
            {"id": "a", "type": "neuron", "origin": "user"},
            {"id": "b", "type": "neuron", "origin": "user"}
        ],
        "edges": [edge, edge]
    }
    with pytest.raises(PayloadValidationError, match="Duplicate edge"):
        validator._parse_graph_payload(payload)

def test_graph_not_connected(validator):
    graph = GraphPayload(
        nodes=[Node("a", "neuron", "origin"), Node("b", "neuron", "origin")],
        edges=[]  # no edge to connect them
    )
    with pytest.raises(PayloadValidationError, match="not fully connected"):
        validator._verify_graph_connected(graph)

@pytest.mark.asyncio
async def test_verify_block_ranges_valid(monkeypatch, validator):
    # patch the constant so our ranges pass
    monkeypatch.setattr(
        "patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT",
        1_000_000
    )

    block_numbers = [1_000_000, 2_000_000, 3_000_000]
    max_block = 4_000_000
    # should not raise
    await validator._verify_block_ranges(block_numbers, max_block)

@pytest.mark.asyncio
async def test_verify_block_ranges_with_invalid_blocks(monkeypatch, validator):
    monkeypatch.setattr(
        "patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT",
        1_000_000
    )

    block_numbers = [999_999, 1_500_000, 5_000_000]  # first too low, last too high
    max_block = 4_000_000

    with pytest.raises(PayloadValidationError) as excinfo:
        await validator._verify_block_ranges(block_numbers, max_block)

    msg = str(excinfo.value)
    assert "invalid block" in msg
    assert "999999" in msg
    assert "5000000" in msg

@pytest.mark.asyncio
async def test_verify_edge_data_success(monkeypatch, validator):
    # one edge, owner‐checker returns it, block check passes
    evidence = TransferEvidence(rao_amount=100, block_number=5_000_000)
    edge = Edge(
        coldkey_source="a",
        coldkey_destination="b",
        category="balance",
        type="transfer",
        evidence=evidence
    )
    graph_payload = GraphPayload(
        nodes=[Node("a", "type", "origin"), Node("b", "type", "origin")],
        edges=[edge]
    )

    class MockEventChecker:
        async def check_events_by_hash(self, event_data_list):
            return event_data_list

    # swap in event_checker and stub out block‐range check
    validator.event_checker = MockEventChecker()
    validator._verify_block_ranges = AsyncMock()

    # should return a list of length 1 (one edge)
    result = await validator._verify_edge_data(graph_payload, max_block_number=6_000_000)
    assert len(result) == 1

def test_generate_adjacency_graph_basic(validator):
    evt = {"coldkey_source": "A", "coldkey_destination": "B"}
    graph = validator._generate_adjacency_graph_from_events([evt])

    assert set(graph.keys()) == {"A", "B"}
    assert {"neighbor": "B", "event": evt} in graph["A"]
    assert {"neighbor": "A", "event": evt} in graph["B"]

def test_generate_adjacency_graph_zero_rao_amount(validator):
    evt = {"coldkey_source": "A", "coldkey_destination": "B", "evidence": {"rao_amount": 0}}
    graph = validator._generate_adjacency_graph_from_events([evt])
    assert graph == {}

def test_generate_adjacency_graph_with_owner(validator):
    evt = {
        "coldkey_source": "A",
        "coldkey_destination": "B",
        "coldkey_owner": "C"
    }
    graph = validator._generate_adjacency_graph_from_events([evt])

    # A, B, C fully interconnected
    assert set(graph.keys()) == {"A", "B", "C"}
    assert {c["neighbor"] for c in graph["A"]} == {"B", "C"}
    assert {c["neighbor"] for c in graph["B"]} == {"A", "C"}
    assert {c["neighbor"] for c in graph["C"]} == {"A", "B"}

def test_generate_adjacency_graph_missing_fields(validator):
    evt = {"coldkey_owner": "X"}  # no src/dst → no edges
    graph = validator._generate_adjacency_graph_from_events([evt])
    assert graph == {}

def test_generate_subgraph_volume_simple(validator):
    evt1 = {
        "coldkey_source": "A", "coldkey_destination": "B",
        "edge_category": "cat1", "edge_type": "t1",
        "rao_amount": 10, "block_number": 1,
    }
    evt2 = {
        "coldkey_source": "B", "coldkey_destination": "C",
        "edge_category": "cat2", "edge_type": "t2",
        "rao_amount": 20, "block_number": 2,
    }
    adj = {
        "A": [{"neighbor": "B", "event": evt1}],
        "B": [{"neighbor": "A", "event": evt1}, {"neighbor": "C", "event": evt2}],
        "C": [{"neighbor": "B", "event": evt2}],
    }
    vol = validator._generate_subgraph_volume_from_adjacency_graph(adj, "A")
    assert vol == 5  # 3 nodes + 2 unique edges

def test_generate_subgraph_volume_isolated_node(validator):
    vol = validator._generate_subgraph_volume_from_adjacency_graph({}, "Z")
    assert vol == 1  # just the start node

def test_calculate_validated_volume_simple(validator):
    evt = {
        "coldkey_source": "A", "coldkey_destination": "B", "coldkey_owner": None,
        "edge_category": "cat", "edge_type": "t", "rao_amount": 5, "block_number": 10,
    }
    vol = validator._calculate_validated_volume([evt], "A")
    assert vol == 3  # A, B, plus one edge

def test_calculate_validated_volume_no_events(validator):
    vol = validator._calculate_validated_volume([], "X")
    assert vol == 1  # only X

def test_calculate_validated_volume_with_owner(validator):
    evt = {
        "coldkey_source": "A", "coldkey_destination": "B", "coldkey_owner": "C",
        "edge_category": "cat", "edge_type": "t", "rao_amount": 1, "block_number": 100,
    }
    vol = validator._calculate_validated_volume([evt], "A")
    assert vol == 4  # nodes A,B,C + single event