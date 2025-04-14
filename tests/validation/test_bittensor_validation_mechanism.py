import pytest
from unittest.mock import AsyncMock
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.protocol import GraphPayload
from patrol.validation.graph_validation.errors import ErrorPayload


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

    event_processer = AsyncMock()
    event_processer.process_event_data.return_value = list(event_fetcher.fetch_all_events.return_value.values())[0]

    validator = BittensorValidationMechanism(event_fetcher, event_processer)

    result = await validator.validate_payload(uid=1, payload=valid_payload, target="B", max_block_number=3014343)

    assert isinstance(result, GraphPayload)
    assert len(result.nodes) == 2
    assert len(result.edges) == 1


async def test_validate_payload_target_missing(valid_payload):
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())

    error = await validator.validate_payload(2, valid_payload, "Z", max_block_number=3014343)

    assert isinstance(error, ErrorPayload)
    assert "Target not found" in error.message


async def test_parse_graph_payload_duplicate_nodes():
    payload = {
        "nodes": [
            {"id": "A", "type": "wallet", "origin": "bittensor"},
            {"id": "A", "type": "wallet", "origin": "bittensor"},
        ],
        "edges": []
    }
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())

    error = await validator.validate_payload(1, payload, "B")

    assert isinstance(error, ErrorPayload)
    assert "Duplicate node" in error.message


async def test_verify_graph_connected_failure():
    validator = BittensorValidationMechanism(AsyncMock(), AsyncMock())

    graph_payload = {
        "nodes": [
            {"id": "A", "type": "wallet", "origin": "bittensor"},
            {"id": "B", "type": "wallet", "origin": "bittensor"},
            {"id": "C", "type": "wallet", "origin": "bittensor"},
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

    error = await validator.validate_payload(1, graph_payload, "B")

    assert isinstance(error, ErrorPayload)
    assert "not fully connected" in error.message


async def test_verify_edge_data_missing_pass(valid_payload):
    event_fetcher = AsyncMock()
    event_fetcher.fetch_all_events.return_value = {3014342: []}

    event_processer = AsyncMock()
    event_processer.process_event_data.return_value = []

    validator = BittensorValidationMechanism(event_fetcher, event_processer)

    success = await validator.validate_payload(1, valid_payload, "B", max_block_number=3014343)

    assert isinstance(success, GraphPayload)


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

    error = await validator.validate_payload(1, valid_payload, "B", max_block_number=3014343)

    assert isinstance(error, ErrorPayload)
    assert "edges not found" in error.message


async def test_verify_block_ranges_out_of_bounds(valid_payload):
    event_fetcher = AsyncMock()
    event_processer = AsyncMock()

    validator = BittensorValidationMechanism(event_fetcher, event_processer)

    error = await validator.validate_payload(1, valid_payload, "B", max_block_number=3000000)

    assert isinstance(error, ErrorPayload)
    assert "invalid block(s) outside the allowed range" in error.message
