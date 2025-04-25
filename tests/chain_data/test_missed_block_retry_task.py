import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from patrol.chain_data.missed_block_retry_task import MissedBlocksRetryTask


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for the MissedBlocksRetryTask."""
    event_fetcher = AsyncMock()
    event_processor = AsyncMock()
    event_repository = AsyncMock()
    missed_blocks_repository = AsyncMock()

    return {
        "event_fetcher": event_fetcher,
        "event_processor": event_processor,
        "event_repository": event_repository,
        "missed_blocks_repository": missed_blocks_repository
    }


@pytest.fixture
def retry_task(mock_dependencies):
    """Create a MissedBlocksRetryTask instance with mock dependencies."""
    task = MissedBlocksRetryTask(
        event_fetcher=mock_dependencies["event_fetcher"],
        event_processor=mock_dependencies["event_processor"],
        event_repository=mock_dependencies["event_repository"],
        missed_blocks_repository=mock_dependencies["missed_blocks_repository"],
        retry_interval_seconds=0.1  # Short interval for testing
    )
    return task


@pytest.mark.asyncio
async def test_retry_task_initialization(retry_task, mock_dependencies):
    """Test that the MissedBlocksRetryTask initializes correctly."""
    assert retry_task.event_fetcher is mock_dependencies["event_fetcher"]
    assert retry_task.event_processor is mock_dependencies["event_processor"]
    assert retry_task.event_repository is mock_dependencies["event_repository"]
    assert retry_task.missed_blocks_repository is mock_dependencies["missed_blocks_repository"]
    assert retry_task.retry_interval_seconds == 0.1
    assert retry_task.batch_size == 25
    assert retry_task.buffer_size == 1000
    assert retry_task.running is False


@pytest.mark.asyncio
async def test_convert_to_db_format_transfer_event(retry_task):
    """Test converting a transfer event to database format."""
    event = {
        "coldkey_source": "source_key",
        "coldkey_destination": "dest_key",
        "category": "balance", 
        "type": "transfer",
        "evidence": {
            "block_number": 4267456,
            "rao_amount": 1000000
        }
    }

    result = retry_task._convert_to_db_format(event)

    assert result["coldkey_source"] == "source_key"
    assert result["coldkey_destination"] == "dest_key"
    assert result["edge_category"] == "balance"
    assert result["edge_type"] == "transfer"
    assert result["block_number"] == 4267456
    assert result["rao_amount"] == 1000000


@pytest.mark.asyncio
async def test_convert_to_db_format_stake_event(retry_task):
    """Test converting a stake event to database format."""
    event = {
        "coldkey_source": "source_key",
        "coldkey_destination": "dest_key",
        "category": "staking",
        "type": "add",
        "evidence": {
            "block_number": 4267856,
            "rao_amount": 2000000,
            "destination_net_uid": 1,
            "alpha_amount": 1000,
            "delegate_hotkey_destination": "dest_hotkey"
        }
    }

    result = retry_task._convert_to_db_format(event)

    assert result["coldkey_source"] == "source_key"
    assert result["coldkey_destination"] == "dest_key"
    assert result["edge_category"] == "staking"
    assert result["edge_type"] == "add"
    assert result["block_number"] == 4267856
    assert result["rao_amount"] == 2000000
    assert result["destination_net_uid"] == 1
    assert result["alpha_amount"] == 1000
    assert result["delegate_hotkey_destination"] == "dest_hotkey"


@pytest.mark.asyncio
async def test_retry_missed_blocks_no_blocks(retry_task, mock_dependencies):
    """Test retry when there are no missed blocks."""
    # Set up the repository to return no missed blocks
    mock_dependencies["missed_blocks_repository"].get_all_missed_blocks.return_value = set()
    
    # Run the retry method
    await retry_task._retry_missed_blocks()
    
    # Verify the repository was queried but no further processing happened
    mock_dependencies["missed_blocks_repository"].get_all_missed_blocks.assert_awaited_once()
    mock_dependencies["event_fetcher"].stream_all_events.assert_not_awaited()
    mock_dependencies["event_processor"].process_event_data.assert_not_awaited()
    mock_dependencies["event_repository"].add_events.assert_not_awaited()
    mock_dependencies["missed_blocks_repository"].remove_blocks.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_missed_blocks_with_blocks(retry_task, mock_dependencies):
    """Test retrying missed blocks that are successfully processed."""
    # Set up the repository to return some missed blocks
    missed_blocks = {4267256, 4267356, 4267456}
    mock_dependencies["missed_blocks_repository"].get_all_missed_blocks.return_value = missed_blocks
    
    # Setup the event fetcher to return some events
    mock_events = {
        4267256: [{"event": {"Balances": [{"Transfer": {"from": ["source1"], "to": ["dest1"], "amount": 1000}}]}}],
        4267356: [{"event": {"SubtensorModule": [{"StakeAdded": [["coldkey2"], ["hotkey2"], 2000, 500, 1]}]}}]
    }
    
    # Create a function to simulate the stream_all_events behavior
    async def fake_stream(block_numbers, queue, missed_blocks_list, batch_size):
        assert set(block_numbers) == missed_blocks
        assert batch_size == retry_task.batch_size
        
        for blk, ev in mock_events.items():
            await queue.put({blk: ev})
        await queue.put(None)  # signal completion
    
    mock_dependencies["event_fetcher"].stream_all_events = AsyncMock(side_effect=fake_stream)
    
    # Setup the event processor to return some processed events
    processed_events = [
        {
            "coldkey_source": "source1",
            "coldkey_destination": "dest1",
            "category": "balance",
            "type": "transfer",
            "evidence": {"block_number": 4267256, "rao_amount": 1000}
        },
        {
            "coldkey_source": "coldkey2",
            "coldkey_destination": "dest_coldkey2",
            "category": "staking",
            "type": "add",
            "evidence": {
                "block_number": 4267356,
                "rao_amount": 2000,
                "delegate_hotkey_destination": "hotkey2",
                "alpha_amount": 500,
                "destination_net_uid": 1
            }
        }
    ]
    
    mock_dependencies["event_processor"].process_event_data.return_value = processed_events
    
    # Run the retry method
    await retry_task._retry_missed_blocks()
    
    # Verify all the steps were called correctly
    mock_dependencies["missed_blocks_repository"].get_all_missed_blocks.assert_awaited_once()
    mock_dependencies["event_fetcher"].stream_all_events.assert_awaited_once()
    mock_dependencies["event_processor"].process_event_data.assert_awaited_once()
    mock_dependencies["event_repository"].add_events.assert_awaited_once()
    
    # Should have removed only the successful blocks (4267256 and 4267356)
    mock_dependencies["missed_blocks_repository"].remove_blocks.assert_awaited_once()
    removed_blocks = mock_dependencies["missed_blocks_repository"].remove_blocks.call_args[0][0]
    assert set(removed_blocks) == {4267256, 4267356}
