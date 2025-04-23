import json
import os
import tempfile
import pytest
from typing import Dict, Any, List
from patrol.validation.persistence.event_store_repository import _ChainEvent, create_event_hash

class MockEventCheckerRepository:
    """
    A mock implementation of EventCheckerRepository that loads events from a JSON file
    instead of using a database.
    """
    
    def __init__(self, events_file_path: str):
        """
        Initialize the mock repository with a path to a JSON file containing events.
        
        Args:
            events_file_path: Path to the JSON file containing event data
        """
        self.events_file_path = events_file_path
        self.events = self._load_events()
        
    def _load_events(self) -> List[Dict[str, Any]]:
        """Load events from the JSON file and return as a list of dictionaries."""
        with open(self.events_file_path, 'r') as f:
            return json.load(f)
    
    async def check_events_by_hash(self, event_data_list: List[Dict[str, Any]]) -> int:
        """
        Check if events exist in the mock database (JSON file) by their hash.
        
        Args:
            event_data_list: List of event data dictionaries
            
        Returns:
            The number of events that don't exist in the mock database
        """
        # Convert incoming events to EventStore objects with hashes
        incoming_events = [_ChainEvent.from_event(data) for data in event_data_list]
        
        # Extract hashes from incoming events
        incoming_hashes = [event.edge_hash for event in incoming_events]
        
        # Convert stored events to EventStore objects and extract their hashes
        stored_events = [_ChainEvent.from_event(data) for data in self.events]
        existing_hashes = {event.edge_hash for event in stored_events}
        
        # Count events that don't exist in the mock database
        unmatched_count = sum(1 for event_hash in incoming_hashes if event_hash not in existing_hashes)
        
        return unmatched_count


@pytest.fixture
def sample_events():
    return [
        {
            "node_id": "node1",
            "node_type": "type1",
            "node_origin": "origin1",
            "coldkey_source": "source1",
            "coldkey_destination": "dest1",
            "edge_category": "category1",
            "edge_type": "type1",
            "evidence_type": "transfer",
            "block_number": 1000,
            "rao_amount": 1000000
        },
        {
            "node_id": "node2",
            "node_type": "type2",
            "node_origin": "origin2",
            "coldkey_source": "source2",
            "coldkey_destination": "dest2",
            "edge_category": "category2",
            "edge_type": "type2",
            "evidence_type": "transfer",
            "block_number": 2000,
            "rao_amount": 2000000
        }
    ]


@pytest.fixture
def events_file(sample_events):
    # Create a temporary JSON file with sample events
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
    json.dump(sample_events, temp_file)
    temp_file.close()
    
    yield temp_file.name
    
    # Clean up after the test
    os.unlink(temp_file.name)


@pytest.fixture
def mock_repository(events_file):
    return MockEventCheckerRepository(events_file)


@pytest.mark.asyncio
async def test_check_existing_event(mock_repository, sample_events):
    # Test with an event that exists in the file
    existing_event = sample_events[0].copy()
    
    # Run the check_events_by_hash method
    result = await mock_repository.check_events_by_hash([existing_event])
    
    # Assert that the existing event is found (0 unmatched)
    assert result == 0


@pytest.mark.asyncio
async def test_check_new_event(mock_repository):
    # Test with a new event that doesn't exist in the file
    new_event = {
        "node_id": "node3",
        "node_type": "type3",
        "node_origin": "origin3",
        "coldkey_source": "source3",
        "coldkey_destination": "dest3",
        "edge_category": "category3",
        "edge_type": "type3",
        "evidence_type": "transfer",
        "block_number": 3000,
        "rao_amount": 3000000
    }
    
    # Run the check_events_by_hash method
    result = await mock_repository.check_events_by_hash([new_event])
    
    # Assert that the new event is not found (1 unmatched)
    assert result == 1


@pytest.mark.asyncio
async def test_check_mixed_events(mock_repository, sample_events):
    # Test with both existing and new events
    existing_event = sample_events[0].copy()
    new_event = {
        "node_id": "node3",
        "node_type": "type3",
        "node_origin": "origin3",
        "coldkey_source": "source3",
        "coldkey_destination": "dest3",
        "edge_category": "category3",
        "edge_type": "type3",
        "evidence_type": "transfer",
        "block_number": 3000,
        "rao_amount": 3000000
    }
    
    # Run the check_events_by_hash method
    result = await mock_repository.check_events_by_hash([existing_event, new_event])
    
    # Assert that when checking both, only one is unmatched
    assert result == 1