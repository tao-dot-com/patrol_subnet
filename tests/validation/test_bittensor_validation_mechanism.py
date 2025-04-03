import asyncio
import pytest
import bittensor as bt
from patrol.constants import Constants
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from substrateinterface import SubstrateInterface
from collections import defaultdict

# --- Fake classes to simulate external dependencies ---

class FakeSubstrate:
    def is_valid_ss58_address(self, addr):
        # For testing, any nonempty string is valid.
        return isinstance(addr, str) and bool(addr)
    
    async def get_block_hash(self, block_id):
        return f"block_hash_{block_id}"
    
    def get_events(self, block_hash):
        # For a valid transfer edge, if block_hash matches, return one valid event.
        if block_hash == "block_hash_1":
            # Create a fake event with a nested 'value' attribute.
            class FakeEvent:
                def __init__(self, value):
                    self.value = value
            event_value = {
                'event_id': 'Transfer',
                'attributes': {
                    'from': 'source_valid',
                    'to': 'dest_valid',
                    'amount': 200
                }
            }
            fake_event = {'event': FakeEvent(event_value)}
            return [fake_event]
        return []
    
    async def query(self, module, storage_function, params=None, block_hash=None):
        # For parent-child edge validation.
        if storage_function == "ChildKeys":

            return [(50, b'child_valid')]
        # For other queries, return an object with empty value.
        class DummyQuery:
            value = []
        return DummyQuery()

class FakeAsyncSubtensor:
    async def __aenter__(self):
        self.substrate = FakeSubstrate()
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def get_stake_for_coldkey(self, coldkey_ss58, block_hash):
        # For staking validation: if coldkey is "source_valid", return a stake with hotkey "dest_valid" and amount 300.
        class FakeStakeValue:
            def __init__(self, rao):
                self.rao = rao
        class FakeStake:
            def __init__(self, hotkey, coldkey, stake_amount):
                self.hotkey_ss58 = hotkey
                self.coldkey_ss58 = coldkey
                self.netuid = 1
                self.stake = FakeStakeValue(stake_amount)
        if coldkey_ss58 == "source_valid":
            return [FakeStake("dest_valid", "source_valid", 300)]
        return []

# A fake SubstrateInterface to override the actual one used in transaction validation.
class FakeSubstrateInterface:
    def __init__(self, url):
        self.url = url
    def get_events(self, block_hash):
        # For a valid transaction, if block_hash matches, return one valid event.
        if block_hash == "block_hash_1":
            class FakeEvent:
                def __init__(self, value):
                    self.value = value
            event_value = {
                'event_id': 'Transfer',
                'attributes': {
                    'from': 'source_valid',
                    'to': 'dest_valid',
                    'amount': 200
                }
            }
            fake_event = {'event': FakeEvent(event_value)}
            return [fake_event]
        return []

# --- Pytest fixture to monkeypatch external dependencies ---
@pytest.fixture(autouse=True)
def patch_external(monkeypatch):
    # Patch bt.AsyncSubtensor to use our fake implementation.
    monkeypatch.setattr(bt, "AsyncSubtensor", lambda network: FakeAsyncSubtensor())
    # Patch SubstrateInterface so that its get_events method returns our fake events.
    monkeypatch.setattr(SubstrateInterface, "__init__", lambda self, url: None)
    monkeypatch.setattr(SubstrateInterface, "get_events", lambda self, block_hash: FakeSubstrateInterface("").get_events(block_hash))

# --- Test Cases ---

@pytest.mark.asyncio
async def test_validate_payload_invalid_structure():
    """
    Ensure that a payload which is None or missing required keys returns default validation results.
    """
    bvm = BittensorValidationMechanism()
    # Test with None payload.
    result = await bvm.validate_payload(uid=1, payload=None)
    assert result['nodes'] == []
    assert result['edges'] == []
    assert result['is_connected'] is False

    # Test with payload missing the 'edges' key.
    invalid_payload = {"nodes": []}
    result = await bvm.validate_payload(uid=1, payload=invalid_payload)
    assert result['nodes'] == []
    assert result['edges'] == []
    assert result['is_connected'] is False

@pytest.mark.asyncio
async def test_validate_payload_valid():
    """
    Provide a valid payload (with nodes and a transfer edge) and ensure that
    node and edge validations succeed and the graph is marked as connected.
    """
    bvm = BittensorValidationMechanism()
    # Create a valid payload with two nodes and one transfer edge.
    payload = {
        "nodes": [
            {"id": "source_valid", "type": "wallet", "origin": "bittensor"},
            {"id": "dest_valid", "type": "wallet", "origin": "bittensor"}
        ],
        "edges": [
            {"source": "source_valid", "destination": "dest_valid", "type": "transfer",
             "evidence": {"block_number": 1, "amount": 200}}
        ]
    }
    # Validate payload with target "source_valid" (which exists).
    result = await bvm.validate_payload(uid=1, payload=payload, target="source_valid")
    # Check that all node validations are True.
    for i in range(len(payload["nodes"])):
        assert bvm.get_node_validation(i) is True
    # Check that the edge validation is True.
    for i in range(len(payload["edges"])):
        assert bvm.get_edge_validation(i) is True
    # The connectivity check should pass.
    assert result['is_connected'] is True

def test_validate_node_structure_invalid():
    """
    Verify that nodes missing required fields or with wrong types fail structure validation.
    """
    bvm = BittensorValidationMechanism()
    # Node missing the 'origin' field.
    invalid_node = {"id": "node1", "type": "wallet"}
    assert bvm.validate_node_structure(invalid_node) is False
    # Node with a non-string 'id'.
    invalid_node2 = {"id": 123, "type": "wallet", "origin": "bittensor"}
    assert bvm.validate_node_structure(invalid_node2) is False

def test_validate_edge_structure_invalid():
    """
    Verify that edges missing required fields fail the structure validation.
    """
    bvm = BittensorValidationMechanism()
    # For a transfer edge missing the 'evidence' field.
    invalid_edge = {"source": "A", "destination": "B", "type": "transfer"}
    assert bvm.validate_edge_structure(invalid_edge) is False

@pytest.mark.asyncio
async def test_validate_staking_data():
    """
    Create a staking edge that should pass validation.
    """
    bvm = BittensorValidationMechanism()
    # Construct a fake staking edge.
    edge = {
        "source": "source_valid",
        "destination": "dest_valid",
        "type": "staking",
        "evidence": {"block_number": 1, "amount": 300}
    }
    async with bt.AsyncSubtensor(network=Constants.ARCHIVE_NODE_ADDRESS) as subtensor:
        result = await bvm.validate_staking_data(edge, subtensor)
        assert result is True

@pytest.mark.asyncio
async def test_validate_transaction_data():
    """
    Create a transfer edge that should pass transaction data validation.
    """
    bvm = BittensorValidationMechanism()
    # Construct a valid transfer edge.
    edge = {
        "source": "source_valid",
        "destination": "dest_valid",
        "type": "transfer",
        "evidence": {"block_number": 1, "amount": 200}
    }
    async with bt.AsyncSubtensor(network=Constants.ARCHIVE_NODE_ADDRESS) as subtensor:
        result = await bvm.validate_transaction_data(edge, subtensor)
        assert result is True

@pytest.mark.asyncio
async def test_validate_parent_child_data(monkeypatch):
    """
    Create a parent-child edge that should pass validation.
    """
    monkeypatch.setattr(Constants, "U64_MAX", 100)
    monkeypatch.setattr(
        "patrol.validation.bittensor_validation_mechanism.decode_account_id",
        lambda x: x.decode() if isinstance(x, bytes) else x
    )
    bvm = BittensorValidationMechanism()
    # For testing, we set allocation to 50 / Constants.U64_MAX.
    # (Assume Constants.U64_MAX is set appropriately; if needed, monkeypatch it.)
    edge = {
        "parent": "parent_valid",
        "child": "child_valid",
        "type": "parent-child",
        "evidence": {"subnet_id": 0, "block_number": 1, "allocation": 50 / 100}  # e.g. 0.5 if U64_MAX is 100
    }
    async with bt.AsyncSubtensor(network=Constants.ARCHIVE_NODE_ADDRESS) as subtensor:
        result = await bvm.validate_parent_child_data(edge, subtensor)
        assert result is True

def test_validate_graph_is_fully_connected():
    """
    Test the connectivity function by simulating validated nodes and edges.
    """
    bvm = BittensorValidationMechanism()
    # Simulate original node data.
    bvm.nodes = [
        {"id": "A", "type": "wallet", "origin": "bittensor"},
        {"id": "B", "type": "wallet", "origin": "bittensor"},
        {"id": "C", "type": "wallet", "origin": "bittensor"}
    ]
    # Simulate validation results marking all nodes and edges as valid.
    bvm.validation_results = {
        "nodes": [True, True, True],
        "edges": [True, True]
    }
    # Create edges that connect A-B and B-C (all nodes connected).
    bvm.edges = [
        {"source": "A", "destination": "B", "type": "transfer", "evidence": {"block_number": 1, "amount": 100}},
        {"source": "B", "destination": "C", "type": "transfer", "evidence": {"block_number": 2, "amount": 100}}
    ]
    assert bvm.validate_graph_is_fully_connected("A") is True

    # Now simulate a disconnected graph (e.g. remove edge connecting C).
    bvm.edges = [
        {"source": "A", "destination": "B", "type": "transfer", "evidence": {"block_number": 1, "amount": 100}}
    ]
    assert bvm.validate_graph_is_fully_connected("A") is False