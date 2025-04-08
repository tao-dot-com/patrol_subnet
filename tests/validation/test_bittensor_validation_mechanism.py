import pytest
from unittest.mock import AsyncMock
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.graph_validation.errors import PayloadValidationError
from patrol.protocol import GraphPayload, Node, Edge

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
                    "block_number": 3014342,
                    "delegate_hotkey_destination": "B",
                    "alpha_amount": 1,
                    "destination_net_uid": 1
                }
            }
        ]
    }

@pytest.mark.asyncio
async def test_validate_payload_success(valid_payload):
    event_fetcher = AsyncMock()
    event_fetcher.fetch_all_events.return_value = {
        3014342: [{
            "coldkey_source": "A",
            "coldkey_destination": "B",
            "coldkey_owner": None,
            "category": "staking",
            "type": "add",
            "evidence": {
                "rao_amount": 10,
                "block_number": 3014342,
                "delegate_hotkey_destination": "B",
                "alpha_amount": 1,
                "destination_net_uid": 1,
                "source_net_uid": None,
                "delegate_hotkey_source": None,
            }
        }]
    }
    event_fetcher.get_current_block.return_value = 3014348

    event_processer = AsyncMock()
    event_processer.process_event_data.return_value = list(event_fetcher.fetch_all_events.return_value.values())[0]

    validator = BittensorValidationMechanism(event_fetcher, event_processer)
    result = await validator.validate_payload(uid=1, payload=valid_payload, target="B")

    assert isinstance(result, GraphPayload)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1

@pytest.mark.asyncio
async def test_validate_payload_target_missing(valid_payload):
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())
    validator.parse_graph_payload(valid_payload)
    with pytest.raises(PayloadValidationError, match="Target not found"):
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
        nodes=[
            Node(id="A", type="wallet", origin="bittensor"),
            Node(id="B", type="wallet", origin="bittensor")
        ],
        edges=[],
    )
    with pytest.raises(ValueError, match="not fully connected"):
        validator.verify_graph_connected()

@pytest.mark.asyncio
async def test_verify_edge_data_missing_pass(valid_payload):
    event_fetcher = AsyncMock()
    event_fetcher.fetch_all_events.return_value = {3014342: []}
    event_fetcher.get_current_block.return_value = 3014348

    event_processer = AsyncMock()
    event_processer.process_event_data.return_value = []

    validator = BittensorValidationMechanism(event_fetcher, event_processer)
    validator.parse_graph_payload(valid_payload)
    await validator.verify_edge_data()  # No error, block not found, edge skipped

@pytest.mark.asyncio
async def test_verify_edge_fail(valid_payload):
    event_fetcher = AsyncMock()
    event_fetcher.fetch_all_events.return_value = {3014342: []}
    event_fetcher.get_current_block.return_value = 3014348

    event_processer = AsyncMock()
    event_processer.process_event_data.return_value = [{
        "coldkey_source": "X",
        "coldkey_destination": "Y",
        "category": "staking",
        "type": "add",
        "evidence": {
            "rao_amount": 99,
            "block_number": 3014342,
            "delegate_hotkey_destination": "B",
            "alpha_amount": 2,
            "destination_net_uid": 1
        }
    }]

    validator = BittensorValidationMechanism(event_fetcher, event_processer)
    validator.parse_graph_payload(valid_payload)
    with pytest.raises(PayloadValidationError, match="edges not found"):
        await validator.verify_edge_data()

# ✅ New Test: Block number out of range
@pytest.mark.asyncio
async def test_verify_block_ranges_out_of_bounds(valid_payload):
    event_fetcher = AsyncMock()
    event_fetcher.get_current_block.return_value = 3000000  # BELOW edge block_number 3014342

    event_processer = AsyncMock()

    validator = BittensorValidationMechanism(event_fetcher, event_processer)
    validator.parse_graph_payload(valid_payload)

    with pytest.raises(PayloadValidationError, match="invalid block\\(s\\) outside the allowed range"):
        await validator.verify_edge_data()