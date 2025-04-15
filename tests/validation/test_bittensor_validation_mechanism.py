import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.protocol import Node, Edge, TransferEvidence, GraphPayload
from patrol.validation.miner_scoring import ValidationResult
from patrol.validation.graph_validation.errors import PayloadValidationError, SingleNodeResponse

@pytest.mark.asyncio
async def test_validate_payload_empty():
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
    result = await validator.validate_payload(uid=1, payload=None)
    assert not result.validated
    assert "Empty/Null" in result.message

@pytest.mark.asyncio
async def test_validate_payload_single_node():
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
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

    fake_fetcher = MagicMock()
    fake_processor = MagicMock()
    validator = BittensorValidationMechanism(fake_fetcher, fake_processor)

    # Mock internal calls
    validator._verify_edge_data = AsyncMock()
    fake_processor.process_event_data = AsyncMock(return_value=[{}])
    fake_fetcher.stream_all_events = AsyncMock(return_value=None)

    result = await validator.validate_payload(uid=1, payload=payload, target="a", max_block_number=6000000)
    assert result.validated
    assert result.volume == 3  # 2 nodes + 1 edge

def test_parse_graph_payload_duplicate_nodes():
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
    payload = {
        "nodes": [{"id": "a", "type": "neuron", "origin": "user"}, {"id": "a", "type": "neuron", "origin": "user"}],
        "edges": []
    }
    with pytest.raises(PayloadValidationError, match="Duplicate node"):
        validator._parse_graph_payload(payload)

def test_parse_graph_payload_duplicate_edges():
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
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
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
    graph = GraphPayload(
        nodes=[Node("a", "neuron", "origin"), Node("b", "neuron", "origin")],
        edges=[]  # no connecting edge
    )
    with pytest.raises(PayloadValidationError, match="not fully connected"):
        validator._verify_graph_connected(graph)

def test_make_event_key():
    validator = BittensorValidationMechanism(MagicMock(), MagicMock())
    event = {
        "coldkey_source": "a",
        "coldkey_destination": "b",
        "coldkey_owner": "a",
        "category": "staking",
        "type": "delegate",
        "evidence": {
            "rao_amount": 50,
            "block_number": 123,
            "source_net_uid": 5,
            "destination_net_uid": 7
        }
    }
    key, block = validator._make_event_key(event)
    assert isinstance(key, tuple)
    assert block == 123

@pytest.mark.asyncio
async def test_verify_block_ranges_valid(monkeypatch):

    monkeypatch.setattr("patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT", 1000000)
    validator = BittensorValidationMechanism(event_fetcher=None, event_processor=None)
    block_numbers = [1000000, 2000000, 3000000]
    max_block = 4000000

    await validator._verify_block_ranges(block_numbers, max_block)

@pytest.mark.asyncio
def test_verify_block_ranges_with_invalid_blocks(monkeypatch):
    monkeypatch.setattr("patrol.validation.graph_validation.bittensor_validation_mechanism.constants.Constants.LOWER_BLOCK_LIMIT", 1000000)

    validator = BittensorValidationMechanism(event_fetcher=None, event_processor=None)
    block_numbers = [999999, 1500000, 5000000]  # 999999 too low, 5000000 too high
    max_block = 4000000

    with pytest.raises(PayloadValidationError) as excinfo:
        asyncio.run(validator._verify_block_ranges(block_numbers, max_block))

    message = str(excinfo.value)
    assert "invalid block" in message
    assert "999999" in message
    assert "5000000" in message

@pytest.mark.asyncio
async def test_fetch_event_keys(monkeypatch):
    # Create a fake event that matches the expected format
    event = {
        "coldkey_source": "a",
        "coldkey_destination": "b",
        "coldkey_owner": "a",
        "category": "balance",
        "type": "transfer",
        "evidence": {
            "rao_amount": 100,
            "block_number": 5000000,
            "destination_net_uid": 1,
            "source_net_uid": 2,
            "alpha_amount": 3,
            "delegate_hotkey_source": "h1",
            "delegate_hotkey_destination": "h2"
        }
    }

    # Mock the event processor to just return our fake event
    mock_event_processor = MagicMock()
    mock_event_processor.process_event_data = AsyncMock(return_value=[event])

    # Mock stream_all_events to put the event in the queue and then a sentinel
    async def fake_stream_all_events(block_numbers, queue, batch_size):
        await queue.put({5000000: event})
        await queue.put(None)

    mock_event_fetcher = MagicMock()
    mock_event_fetcher.stream_all_events = fake_stream_all_events

    validator = BittensorValidationMechanism(mock_event_fetcher, mock_event_processor, buffer_size=1)

    event_keys, block_numbers = await validator._fetch_event_keys([5000000])

    assert len(event_keys) == 1
    assert 5000000 in block_numbers
    assert isinstance(next(iter(event_keys)), tuple)

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

    # Create a matching event
    matching_event = {
        "coldkey_source": "a",
        "coldkey_destination": "b",
        "coldkey_owner": None,
        "category": "balance",
        "type": "transfer",
        "evidence": {
            "rao_amount": 100,
            "block_number": 5000000,
            "destination_net_uid": None,
            "source_net_uid": None,
            "alpha_amount": None,
            "delegate_hotkey_source": None,
            "delegate_hotkey_destination": None,
        }
    }

    # Mock event processor and fetcher
    mock_event_processor = MagicMock()
    mock_event_processor.process_event_data = AsyncMock(return_value=[matching_event])

    async def fake_stream_all_events(block_numbers, queue, batch_size):
        await queue.put({5000000: matching_event})
        await queue.put(None)

    mock_event_fetcher = MagicMock()
    mock_event_fetcher.stream_all_events = fake_stream_all_events

    validator = BittensorValidationMechanism(mock_event_fetcher, mock_event_processor, buffer_size=1)
    validator._verify_block_ranges = AsyncMock()  # assume block range check passes

    # Should not raise
    await validator._verify_edge_data(graph_payload, max_block_number=6000000)
