import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC

from patrol.chain_data.event_collector import EventCollector
from patrol.constants import Constants


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for the EventCollector."""
    event_fetcher = AsyncMock()
    event_processor = AsyncMock()
    event_repository = AsyncMock()

    return {
        "event_fetcher": event_fetcher,
        "event_processor": event_processor,
        "event_repository": event_repository
    }


@pytest.fixture
def event_collector(mock_dependencies):
    """Create an EventCollector instance with mock dependencies."""
    collector = EventCollector(
        event_fetcher=mock_dependencies["event_fetcher"],
        event_processor=mock_dependencies["event_processor"],
        event_repository=mock_dependencies["event_repository"],
        sync_interval=0.1  # Short interval for testing
    )
    return collector


@pytest.mark.asyncio
async def test_event_collector_initialization(event_collector, mock_dependencies):
    """Test that the EventCollector initializes correctly."""
    assert event_collector.event_fetcher == mock_dependencies["event_fetcher"]
    assert event_collector.event_processor == mock_dependencies["event_processor"]
    assert event_collector.event_repository == mock_dependencies["event_repository"]
    assert event_collector.sync_interval == 0.1
    assert event_collector.running is False
    assert event_collector.last_synced_block is None


@pytest.mark.asyncio
async def test_convert_to_db_format_transfer_event(event_collector):
    """Test converting a transfer event to database format."""
    event = {
        "coldkey_source": "source_key",
        "coldkey_destination": "dest_key",
        "category": "balance", 
        "type": "transfer",
        "evidence": {
            "block_number": 123456,
            "rao_amount": 1000000
        }
    }

    result = event_collector._convert_to_db_format(event)

    assert result["coldkey_source"] == "source_key"
    assert result["coldkey_destination"] == "dest_key"
    assert result["edge_category"] == "balance" 
    assert result["edge_type"] == "transfer"
    assert result["block_number"] == 123456
    assert result["rao_amount"] == 1000000
    assert "destination_net_uid" not in result


@pytest.mark.asyncio
async def test_convert_to_db_format_stake_event(event_collector):
    """Test converting a stake event to database format."""
    event = {
        "coldkey_source": "source_key",
        "coldkey_destination": "dest_key",
        "category": "staking",
        "type": "add",
        "evidence": {
            "block_number": 123456,
            "rao_amount": 2000000,
            "destination_net_uid": 1,
            "alpha_amount": 1000,
            "delegate_hotkey_destination": "dest_hotkey"
        }
    }

    result = event_collector._convert_to_db_format(event)

    assert result["coldkey_source"] == "source_key"
    assert result["coldkey_destination"] == "dest_key"
    assert result["edge_category"] == "staking"
    assert result["edge_type"] == "add"
    assert result["block_number"] == 123456
    assert result["rao_amount"] == 2000000
    assert result["destination_net_uid"] == 1
    assert result["alpha_amount"] == 1000
    assert result["delegate_hotkey_destination"] == "dest_hotkey"
    assert "source_net_uid" in result
    assert result["source_net_uid"] is None


@pytest.mark.asyncio
async def test_fetch_and_store_events(event_collector, mock_dependencies):
    """Test fetching and storing events."""
    # Setup mocks
    start_block = 100
    end_block = 105
    
    # Mock raw event data from EventFetcher
    # block_number: block_events
    mock_events = {
        100: [{"event": {"Balances": [{"Transfer": {"from": ["source1"], "to": ["dest1"], "amount": 1000}}]}}],
        103: [{"event": {"SubtensorModule": [{"StakeAdded": [["coldkey2"], ["hotkey2"], 2000, 500, 1]}]}}]
    }
    
    # Process event data for each block separately
    block_100_processed = [
        {
            "coldkey_source": "source1",
            "coldkey_destination": "dest1",
            "category": "balance",
            "type": "transfer",
            "evidence": {
                "block_number": 100,
                "rao_amount": 1000
            }
        }
    ]
    
    block_103_processed = [
        {
            "coldkey_source": "coldkey2",
            "coldkey_destination": "dest_coldkey2",
            "category": "staking",
            "type": "add",
            "evidence": {
                "block_number": 103,
                "rao_amount": 2000,
                "delegate_hotkey_destination": "hotkey2",
                "alpha_amount": 500,
                "destination_net_uid": 1
            }
        }
    ]

    # Configure mocked fetcher
    mock_dependencies["event_fetcher"].fetch_all_events.return_value = mock_events
    
    # Configure process_event_data to return events from mocked blocks 100 or 103
    def process_event_data_mock(block_data):
        block_number = list(block_data.keys())[0]
        if block_number == 100:
            return block_100_processed
        elif block_number == 103:
            return block_103_processed
        else:
            return []
    mock_dependencies["event_processor"].process_event_data.side_effect = process_event_data_mock

    await event_collector._fetch_and_store_events(start_block, end_block)
    
    # Verify interactions
    mock_dependencies["event_fetcher"].fetch_all_events.assert_called_once_with(
        list(range(start_block, end_block + 1)), 
        batch_size=event_collector.batch_size
    )
    
    # Verify that process_event_data was called for each block
    assert mock_dependencies["event_processor"].process_event_data.call_count == 2
    
    # Verify that add_events was called with the correct number of events
    assert mock_dependencies["event_repository"].add_events.called
    
    events_list = mock_dependencies["event_repository"].add_events.call_args[0][0]
    
    # Verify the list contains 2 events (one from each block)
    assert len(events_list) == 2
    
    # Verify first event (transfer)
    assert events_list[0]["coldkey_source"] == "source1"
    assert events_list[0]["coldkey_destination"] == "dest1"
    assert events_list[0]["edge_category"] == "balance"
    
    # Verify second event (stake)
    assert events_list[1]["coldkey_source"] == "coldkey2"
    assert events_list[1]["coldkey_destination"] == "dest_coldkey2"
    assert events_list[1]["edge_category"] == "staking"



@pytest.mark.asyncio
@pytest.mark.parametrize("highest_block_in_db, current_block, expected_range", [
    (400000, 5000000, 100),  # Large gap - should use max 100 blocks
    (499950, 500000, 50)     # Small gap - should use actual difference (50 blocks)
])
async def test_sync_loop_with_existing_blocks(event_collector, mock_dependencies, highest_block_in_db, current_block, expected_range):
    """Test the sync loop when there are existing blocks in the database."""
    # Setup mocks
    mock_dependencies["event_fetcher"].get_current_block.return_value = current_block
    mock_dependencies["event_repository"].get_highest_block_from_db.return_value = highest_block_in_db
    mock_dependencies["event_fetcher"].fetch_all_events.return_value = {}
    
    # Start the collector and let it run briefly
    await event_collector.start()
    await asyncio.sleep(0.1)  # Allow one iteration of the sync loop
    await event_collector.stop()
    
    # Verify methods called
    mock_dependencies["event_repository"].get_highest_block_from_db.assert_called_once()
    mock_dependencies["event_fetcher"].get_current_block.assert_called()
    mock_dependencies["event_fetcher"].fetch_all_events.assert_called()
    
    # Get the first positional argument (block_numbers)
    call_args = mock_dependencies["event_fetcher"].fetch_all_events.call_args[0][0]
    
    # Check the range of blocks
    # Should start from highest_block_in_db + 1 and not exceed max batch size of 100 blocks
    start_block = highest_block_in_db + 1
    end_block = min(current_block, start_block + 100)
    expected_blocks = list(range(start_block, end_block + 1))
    assert call_args == expected_blocks
    
    # Verify the last_synced_block was updated
    assert event_collector.last_synced_block == min(start_block + expected_range, current_block)


@pytest.mark.asyncio
async def test_sync_loop_with_no_blocks(event_collector, mock_dependencies):
    """Test the sync loop when there are no existing blocks in the database."""
    # Setup mocks
    current_block = 5000000  # Some high block number
    mock_dependencies["event_fetcher"].get_current_block.return_value = current_block
    mock_dependencies["event_repository"].get_highest_block_from_db.return_value = None
    mock_dependencies["event_fetcher"].fetch_all_events.return_value = {}
    
    # Start the collector and let it run briefly
    await event_collector.start()
    await asyncio.sleep(0.1)  # Allow one iteration of the sync loop
    await event_collector.stop()
    
    # Verify methods called
    mock_dependencies["event_repository"].get_highest_block_from_db.assert_called_once()
    mock_dependencies["event_fetcher"].get_current_block.assert_called()
    mock_dependencies["event_fetcher"].fetch_all_events.assert_called()
    
    # Get the first positional argument (block_numbers)
    call_args = mock_dependencies["event_fetcher"].fetch_all_events.call_args[0][0]
    
    # Check the range of blocks
    # Should start from Constants.LOWER_BLOCK_LIMIT
    start_block = Constants.LOWER_BLOCK_LIMIT
    # End block should be start_block + max_blocks (100), but limited by current_block
    end_block = min(current_block, start_block + 100)
    expected_blocks = list(range(start_block, end_block + 1))
    
    assert call_args == expected_blocks
    
    # Verify the last_synced_block was updated
    assert event_collector.last_synced_block == end_block