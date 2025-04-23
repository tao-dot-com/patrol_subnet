import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.protocol import Node, Edge, TransferEvidence, GraphPayload
from patrol.validation.miner_scoring import ValidationResult
from patrol.validation.graph_validation.errors import PayloadValidationError, SingleNodeResponse

@pytest.mark.asyncio
async def test_validate_payload_empty():
    validator = BittensorValidationMechanism(MagicMock())
    result = await validator.validate_payload(uid=1, payload=None)
    assert not result.validated
    assert "Empty/Null" in result.message

@pytest.mark.asyncio
async def test_validate_payload_single_node():
    validator = BittensorValidationMechanism(MagicMock())
    payload = {
        "nodes": [{"id": "a", "type": "neuron", "origin": "user"}],
        "edges": []
    }

    result = await validator.validate_payload(uid=1, payload=payload, target="a")
    assert not result.validated
    assert "Only single node" in result.message

@pytest.mark.asyncio
async def test_validate_payload_valid(monkeypatch):
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

    fake_repository = MagicMock()
    validator = BittensorValidationMechanism(fake_repository)

    # Mock internal calls
    validator._verify_edge_data = AsyncMock()

    result = await validator.validate_payload(uid=1, payload=payload, target="a")
    assert result.validated
    assert result.volume == 3  # 2 nodes + 1 edge

def test_parse_graph_payload_duplicate_nodes():
    validator = BittensorValidationMechanism(MagicMock())
    payload = {
        "nodes": [{"id": "a", "type": "neuron", "origin": "user"}, {"id": "a", "type": "neuron", "origin": "user"}],
        "edges": []
    }
    with pytest.raises(PayloadValidationError, match="Duplicate node"):
        validator._parse_graph_payload(payload)

def test_parse_graph_payload_duplicate_edges():
    validator = BittensorValidationMechanism(MagicMock())
    edge = {
        "coldkey_source": "a",
        "coldkey_destination": "b",
        "category": "balance",
        "type": "transfer",
        "evidence": {
            "rao_amount": 10,
            "block_number": 1000
        }
    }
    payload = {
        "nodes": [{"id": "a", "type": "neuron", "origin": "user"}, {"id": "b", "type": "neuron", "origin": "user"}],
        "edges": [edge, edge]
    }
    with pytest.raises(PayloadValidationError, match="Duplicate edge"):
        validator._parse_graph_payload(payload)

def test_graph_not_connected():
    validator = BittensorValidationMechanism(MagicMock())
    graph = GraphPayload(
        nodes=[Node("a", "neuron", "origin"), Node("b", "neuron", "origin")],
        edges=[]  # no connecting edge
    )
    with pytest.raises(PayloadValidationError, match="not fully connected"):
        validator._verify_graph_connected(graph)

@pytest.mark.asyncio
async def test_verify_block_ranges_valid(monkeypatch):

    monkeypatch.setattr("patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT", 1000000)
    validator = BittensorValidationMechanism(event_store_repository=None)
    block_numbers = [1000000, 2000000, 3000000]
    max_block = 4000000

    await validator._verify_block_ranges(block_numbers, max_block)

@pytest.mark.asyncio
def test_verify_block_ranges_with_invalid_blocks(monkeypatch):
    monkeypatch.setattr("patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT", 1000000)

    validator = BittensorValidationMechanism(event_store_repository=None)
    block_numbers = [999999, 1500000, 5000000]  # 999999 too low, 5000000 too high
    max_block = 4000000

    with pytest.raises(PayloadValidationError) as excinfo:
        asyncio.run(validator._verify_block_ranges(block_numbers, max_block))

    message = str(excinfo.value)
    assert "invalid block" in message
    assert "999999" in message
    assert "5000000" in message

@pytest.mark.asyncio
async def test_verify_edge_data_success(monkeypatch):
    # Create a graph payload with one node and one matching edge
    evidence = TransferEvidence(rao_amount=100, block_number=5000000)
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

    # Mock the event store repository
    mock_event_store_repository = MagicMock()
    # Return 0 unmatched events to indicate all events were found
    mock_event_store_repository.check_events_by_hash = AsyncMock(return_value=0)

    # Create the validator with our mock repository
    validator = BittensorValidationMechanism(mock_event_store_repository)
    validator._verify_block_ranges = AsyncMock()  # assume block range check passes

    # Should not raise any exception
    await validator._verify_edge_data(graph_payload, max_block_number=6000000)

    # Verify the correct method was called with converted event data
    mock_event_store_repository.check_events_by_hash.assert_called_once()
    
    # Optional: verify the converted event data format
    called_args = mock_event_store_repository.check_events_by_hash.call_args[0][0]
    assert len(called_args) == 1  # One event
    assert called_args[0]["coldkey_source"] == "a"
    assert called_args[0]["coldkey_destination"] == "b"
    assert called_args[0]["edge_category"] == "balance"
    assert called_args[0]["edge_type"] == "transfer"
    assert called_args[0]["evidence_type"] == "transfer"
    assert called_args[0]["block_number"] == 5000000
