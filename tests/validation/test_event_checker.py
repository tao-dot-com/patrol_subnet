import pytest
import asyncio
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from patrol.validation.persistence import Base
from patrol.validation.persistence.event_store_repository import _EventStore
from patrol.validation.graph_validation.event_checker_repository import EventChecker

@pytest.fixture
async def in_memory_db():
    """Create an in-memory SQLite database for testing"""
    # Use in-memory SQLite database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Dispose of the engine
    await engine.dispose()

@pytest.fixture
async def repository(in_memory_db):
    """Create a repository with in-memory database"""
    return EventChecker(in_memory_db)

@pytest.fixture
async def populated_db(in_memory_db, sample_events):
    """Populate the in-memory database with sample events"""
    # Create a session
    session_maker = async_sessionmaker(bind=in_memory_db)
    
    async with session_maker() as session:
        # Convert sample events to _EventStore objects
        event_objs = [_EventStore.from_event(event) for event in sample_events]
        
        # Add to database
        session.add_all(event_objs)
        await session.commit()
    
    return in_memory_db


@pytest.fixture
def sample_events():
    """Sample events for testing"""
    return [
        {
            "id": "id1",
            "created_at": datetime(2023, 1, 1, tzinfo=UTC),  # Use actual datetime object
            "node_id": "node1",
            "node_type": "type1",
            "node_origin": "origin1",
            "coldkey_source": "source1",
            "coldkey_destination": "dest1",
            "edge_category": "category1",
            "edge_type": "type1",
            "coldkey_owner": None,
            "evidence_type": "transfer",
            "block_number": 1000,
            "rao_amount": 1000000,
            "destination_net_uid": None,
            "source_net_uid": None,
            "alpha_amount": None,
            "delegate_hotkey_source": None,
            "delegate_hotkey_destination": None
        },
        {
            "id": "id2", 
            "created_at": datetime(2023, 1, 1, tzinfo=UTC),  # Use actual datetime object
            "node_id": "node2",
            "node_type": "type2",
            "node_origin": "origin2",
            "coldkey_source": "source2",
            "coldkey_destination": "dest2",
            "edge_category": "category2",
            "edge_type": "type2",
            "coldkey_owner": None,
            "evidence_type": "transfer",
            "block_number": 2000,
            "rao_amount": 2000000,
            "destination_net_uid": None,
            "source_net_uid": None,
            "alpha_amount": None,
            "delegate_hotkey_source": None,
            "delegate_hotkey_destination": None
        }
    ]

@pytest.mark.asyncio
async def test_check_events_matching(repository, populated_db, sample_events):
    """Test that existing events return an empty list"""
    # Check an event that exists in the database
    existing_event = sample_events[0].copy()
    
    # All events should match (empty list = no unmatched events)
    result = await repository.check_events_by_hash([existing_event])
    assert result == []

@pytest.mark.asyncio
async def test_check_new_event(repository, populated_db):
    """Test that non-existing events return a list with the event"""
    # Create a new event that doesn't exist in the database
    new_event = {
        "id": "id3",
        "created_at": datetime(2023, 1, 1, tzinfo=UTC),
        "node_id": "node3",
        "node_type": "type3",
        "node_origin": "origin3",
        "coldkey_source": "source3",
        "coldkey_destination": "dest3",
        "edge_category": "category3",
        "edge_type": "type3",
        "coldkey_owner": None,
        "evidence_type": "transfer",
        "block_number": 3000,
        "rao_amount": 3000000,
        "destination_net_uid": None,
        "source_net_uid": None,
        "alpha_amount": None,
        "delegate_hotkey_source": None,
        "delegate_hotkey_destination": None
    }
    
    # One unmatched event should be returned
    result = await repository.check_events_by_hash([new_event])
    assert len(result) == 1

@pytest.mark.asyncio
async def test_check_mixed_events(repository, populated_db, sample_events):
    """Test a mix of existing and non-existing events"""
    # One existing, one new
    existing_event = sample_events[0].copy()
    new_event = {
        "id": "id3",
        "created_at": datetime(2023, 1, 1, tzinfo=UTC),
        "node_id": "node3",
        "node_type": "type3",
        "node_origin": "origin3", 
        "coldkey_source": "source3",
        "coldkey_destination": "dest3",
        "edge_category": "category3",
        "edge_type": "type3",
        "coldkey_owner": None,
        "evidence_type": "transfer",
        "block_number": 3000,
        "rao_amount": 3000000,
        "destination_net_uid": None,
        "source_net_uid": None,
        "alpha_amount": None,
        "delegate_hotkey_source": None,
        "delegate_hotkey_destination": None
    }
    
    # Only the new event should be unmatched
    result = await repository.check_events_by_hash([existing_event, new_event])
    assert len(result) == 1