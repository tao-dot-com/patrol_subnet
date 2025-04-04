import pytest
from unittest.mock import AsyncMock, patch
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.graph_validation.errors import PayloadValidationError, ErrorPayload
from patrol.protocol import GraphPayload, Node, Edge, StakeEvidence

@pytest.fixture
def valid_payload():
    return {
        "nodes": [
            {"id": "A", "type": "wallet", "origin": "bittensor"},
            {"id": "B", "type": "wallet", "origin": "bittensor"},
        ],
        "edges": [
            {
                "coldkey_source": "A",
                "coldkey_destination": "B",
                "category": "staking",
                "type": "add",
                "evidence": {
                    "rao_amount": 10,
                    "block_number": 1,
                    "delegate_hotkey_destination": "B",
                    "alpha_amount": 1,
                    "destination_net_uid": 1
                }
            }
        ]
    }

@pytest.mark.asyncio
async def test_validate_payload_success(valid_payload):
    fetcher = AsyncMock()
    fetcher.fetch_all_events.return_value = {
        1: [{"coldkey_source": "A", "coldkey_destination": "B", "category": "staking", "type": "add",
             "evidence": {
                 "rao_amount": 10, "block_number": 1,
                 "delegate_hotkey_destination": "B", "alpha_amount": 1,
                 "destination_net_uid": 1
             }}]
    }
    coldkey_finder = AsyncMock()

    with patch("patrol.validation.graph_validation.bittensor_validation_mechanism.process_event_data", new=AsyncMock(return_value=list(fetcher.fetch_all_events.return_value.values())[0])):
        validator = BittensorValidationMechanism(fetcher, coldkey_finder)
        result = await validator.validate_payload(uid=1, payload=valid_payload, target="B")

    assert isinstance(result, GraphPayload)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1

@pytest.mark.asyncio
async def test_validate_payload_target_missing(valid_payload):
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())
    validator.parse_graph_payload(valid_payload)
    with pytest.raises(PayloadValidationError):
        validator.verify_target_in_graph("Z")

def test_parse_graph_payload_duplicate_nodes():
    payload = {
        "nodes": [
            {"id": "A", "type": "wallet", "origin": "bittensor"},
            {"id": "A", "type": "wallet", "origin": "bittensor"},
        ],
        "edges": []
    }
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())
    with pytest.raises(PayloadValidationError, match="Duplicate node"):
        validator.parse_graph_payload(payload)

def test_verify_graph_connected_failure():
    validator = BittensorValidationMechanism(None, None)
    validator.graph_payload = GraphPayload(
        nodes=[Node(id="A", type="wallet", origin="bittensor"), Node(id="B", type="wallet", origin="bittensor")],
        edges=[],
    )
    with pytest.raises(ValueError, match="not fully connected"):
        validator.verify_graph_connected()

@pytest.mark.asyncio
async def test_verify_edge_data_missing_match(valid_payload):
    fetcher = AsyncMock()
    fetcher.fetch_all_events.return_value = {1: []}
    coldkey_finder = AsyncMock()

    with patch("patrol.validation.graph_validation.bittensor_validation_mechanism.process_event_data", new=AsyncMock(return_value=[])):
        validator = BittensorValidationMechanism(fetcher, coldkey_finder)
        validator.parse_graph_payload(valid_payload)
        with pytest.raises(PayloadValidationError, match="edges not found"):
            await validator.verify_edge_data()