import pytest
import asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from patrol.validation.persistence import Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from patrol.validation.persistence.event_store_repository import (
    DatabaseEventStoreRepository,
    _ChainEvent,
    create_event_hash
)


@pytest.fixture
async def memory_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Close engine
    await engine.dispose()


@pytest.fixture
async def event_repository(memory_db_engine):
    """Create a DatabaseEventStoreRepository with an in-memory database."""
    repository = DatabaseEventStoreRepository(memory_db_engine)
    yield repository


@pytest.mark.asyncio
async def test_create_event_hash():
    """Test that create_event_hash generates consistent hashes."""
    # Create an event with the fields used in create_event_hash
    event = {
        "coldkey_source": "source1",
        "coldkey_destination": "dest1",
        "edge_category": "balance",
        "edge_type": "transfer",
        "block_number": 100,
        "rao_amount": 1000000
    }
    
    # Hash should be the same for the same event
    hash1 = create_event_hash(event)
    hash2 = create_event_hash(event.copy())
    assert hash1 == hash2
    
    # Hash should be different for different events
    event_modified = event.copy()
    event_modified["rao_amount"] = 2000000
    hash3 = create_event_hash(event_modified)
    assert hash1 != hash3


@pytest.mark.asyncio
async def test_add_single_transfer_event(event_repository):
    """Test adding a single event to the repository."""
    # Create a minimal valid event with only the fields in _EventStore
    event = {
        "coldkey_source": "source1",
        "coldkey_destination": "dest1",
        "edge_category": "balance",
        "edge_type": "transfer",
        "coldkey_owner": None,
        "block_number": 100,
        "rao_amount": 1000000
    }
    
    # Add the event
    await event_repository.add_events([event])
    
    # Verify the event was added using a direct query
    async with event_repository.LocalAsyncSession() as session:
        query = select(_ChainEvent)
        result = await session.execute(query)
        events = result.scalars().all()
        
        # Check that we got the event
        assert len(events) == 1
        stored_event = events[0]
        assert stored_event.coldkey_source == "source1"
        assert stored_event.coldkey_destination == "dest1"
        assert stored_event.block_number == 100

@pytest.mark.asyncio
async def test_add_single_stake_event(event_repository):
    """Test adding a stake event with staking-specific fields."""
    # Create a stake event
    event = {
        "coldkey_source": "source1",
        "coldkey_destination": "dest1",
        "edge_category": "staking",
        "edge_type": "add",
        "coldkey_owner": None,
        "block_number": 100,
        "rao_amount": 1000000,
        "destination_net_uid": 1,
        "source_net_uid": 0,
        "alpha_amount": 1000,
        "delegate_hotkey_source": "source_hotkey",
        "delegate_hotkey_destination": "dest_hotkey"
    }
    
    # Add the event
    await event_repository.add_events([event])
    
    # Verify the event was added with all its fields
    async with event_repository.LocalAsyncSession() as session:
        query = select(_ChainEvent)
        result = await session.execute(query)
        events = result.scalars().all()
        
        # Check that we got the event
        assert len(events) == 1
        stored_event = events[0]
        assert stored_event.coldkey_source == "source1"
        assert stored_event.coldkey_destination == "dest1"
        assert stored_event.edge_category == "staking"
        assert stored_event.edge_type == "add"
        assert stored_event.block_number == 100
        assert stored_event.rao_amount == 1000000
        assert stored_event.destination_net_uid == 1
        assert stored_event.source_net_uid == 0
        assert stored_event.alpha_amount == 1000
        assert stored_event.delegate_hotkey_source == "source_hotkey"
        assert stored_event.delegate_hotkey_destination == "dest_hotkey"

@pytest.mark.asyncio
async def test_get_highest_block_from_db(event_repository):
    """Test getting the highest block number from the database."""
    # Initially, there should be no blocks
    highest_block = await event_repository.get_highest_block_from_db()
    assert highest_block is None
    
    # Add an event
    event = {
        "coldkey_source": "source1",
        "coldkey_destination": "dest1",
        "edge_category": "balance",
        "edge_type": "transfer",
        "coldkey_owner": None,
        "block_number": 100,
        "rao_amount": 1000000
    }
    await event_repository.add_events([event])
    
    # Now the highest block should be 100
    highest_block = await event_repository.get_highest_block_from_db()
    assert highest_block == 100
    
    # Add another event with a higher block number
    event2 = event.copy()
    event2["block_number"] = 200
    event2["coldkey_source"] = "source2"
    await event_repository.add_events([event2])
    
    # Now the highest block should be 200
    highest_block = await event_repository.get_highest_block_from_db()
    assert highest_block == 200


@pytest.mark.asyncio
async def test_find_by_coldkey(event_repository):
    """Test finding events by coldkey."""
    # Add some events
    events = [
        {
            "coldkey_source": "source1",
            "coldkey_destination": "dest1",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 100,
            "rao_amount": 1000000
        },
        {
            "coldkey_source": "source2",
            "coldkey_destination": "dest2",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 200,
            "rao_amount": 2000000
        }
    ]
    await event_repository.add_events(events)
    
    # Find events for source1
    events_for_source1 = await event_repository.find_by_coldkey("source1")
    assert len(events_for_source1) == 1
    assert events_for_source1[0].coldkey_source == "source1"  # Access attribute directly on ORM object
    assert events_for_source1[0].block_number == 100
    
    # Find events for dest2
    events_for_dest2 = await event_repository.find_by_coldkey("dest2")
    assert len(events_for_dest2) == 1
    assert events_for_dest2[0].coldkey_destination == "dest2"  # Access attribute directly on ORM object
    assert events_for_dest2[0].block_number == 200
    
    # Find events for nonexistent coldkey
    events_for_nonexistent = await event_repository.find_by_coldkey("nonexistent")
    assert len(events_for_nonexistent) == 0


@pytest.mark.asyncio
async def test_batch_write_success_path(event_repository):
    """Test that events are written using the batch operation when possible."""
    # Create multiple events
    events = [
        {
            "coldkey_source": f"source{i}",
            "coldkey_destination": f"dest{i}",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 100 + i,
            "rao_amount": 1000000 + i
        }
        for i in range(10)  # Create 10 unique events
    ]
    
    # Use patching to monitor which code paths are executed
    with patch('patrol.validation.persistence.event_store_repository.logger.debug') as mock_debug:
        # Add all events at once
        await event_repository.add_events(events)
        
        # Verify the batch operation succeeded and didn't fall back
        fallback_calls = [
            call for call in mock_debug.call_args_list 
            if "falling back to individual inserts" in str(call)
        ]
        assert len(fallback_calls) == 0, "Batch operation fell back to individual inserts"
    
    # Verify all events were added
    async with event_repository.LocalAsyncSession() as session:
        query = select(_ChainEvent)
        result = await session.execute(query)
        stored_events = result.scalars().all()
        assert len(stored_events) == 10


@pytest.mark.asyncio
async def test_batch_write_fallback_path(event_repository):
    """Test that individual writes are used as fallback when batch fails."""
    # First add some initial events
    initial_events = [
        {
            "coldkey_source": f"source{i}",
            "coldkey_destination": f"dest{i}",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 100 + i,
            "rao_amount": 1000000 + i
        }
        for i in range(5)
    ]
    
    await event_repository.add_events(initial_events)
    
    # Now create a batch with 5 duplicates and 5 new events to force fallback
    mixed_batch = [
        {
            "coldkey_source": f"source{i}",
            "coldkey_destination": f"dest{i}",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 100 + i,
            "rao_amount": 1000000 + i
        }
        for i in range(5)
    ] + [
        {
            "coldkey_source": f"source{i+5}",
            "coldkey_destination": f"dest{i+5}",
            "edge_category": "balance",
            "edge_type": "transfer",
            "coldkey_owner": None,
            "block_number": 100 + i + 5,
            "rao_amount": 1000000 + i + 5
        }
        for i in range(5)
    ]
    
    # Use patching to monitor which code paths are executed
    with patch('patrol.validation.persistence.event_store_repository.logger.debug') as mock_debug:
        # Add the mixed batch
        await event_repository.add_events(mixed_batch)
        
        # Verify the fallback path was taken
        fallback_calls = [
            call for call in mock_debug.call_args_list 
            if "falling back to individual inserts" in str(call)
        ]
        assert len(fallback_calls) > 0, "Batch operation didn't fall back to individual inserts"
    
    # Verify the end result
    async with event_repository.LocalAsyncSession() as session:
        query = select(_ChainEvent)
        result = await session.execute(query)
        stored_events = result.scalars().all()
        assert len(stored_events) == 10
        