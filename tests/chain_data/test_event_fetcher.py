
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from patrol.chain_data.event_fetcher import group_block, group_blocks, EventFetcher, GROUP_INIT_BLOCK


# -----------------------------
# Tests for group_block function
# -----------------------------
def test_group_block_boundaries():

    current_block = 5228700

    # Blocks just above the lower boundary for group 1:
    assert group_block(3014341, current_block) == 1
    # Upper boundary of group 1
    assert group_block(3804340, current_block) == 1
    # Next block belongs to group 2
    assert group_block(3804341, current_block) == 2

    # Upper boundary of group 2
    assert group_block(4264340, current_block) == 2
    # Next block belongs to group 3
    assert group_block(4264341, current_block) == 3

    # Upper boundary of group 3
    assert group_block(4920350, current_block) == 3
    # Next block belongs to group 4
    assert group_block(4920351, current_block) == 4

    # Upper boundary of group 4
    assert group_block(5163656, current_block) == 4
    # Next block belongs to group 5
    assert group_block(5163657, current_block) == 5

    # Upper boundary of group 5
    assert group_block(5228684, current_block) == 5
    # Any block greater than 5228684 goes to group 6
    assert group_block(5228685, current_block) == 6

    # Test an edge cases:
    assert group_block(3014340, current_block) == None

    assert group_block(6000000, current_block) == None


# -----------------------------
# Tests for group_blocks function
# -----------------------------
def test_group_blocks_batches_correctly():
    block_numbers = list(range(1000, 1012))
    block_hashes = [f"0xhash{i}" for i in range(len(block_numbers))]
    current_block = 6000000

    # Patch group_block to return group 1 for all inputs
    with patch("patrol.chain_data.event_fetcher.group_block", return_value=1):
        grouped = group_blocks(block_numbers, block_hashes, current_block, batch_size=5)

    assert 1 in grouped
    assert len(grouped[1]) == 3  # 12 blocks => 3 batches of 5, 5, 2
    assert all(isinstance(batch, list) for batch in grouped[1])
    assert grouped[1][0] == [(1000, '0xhash0'), (1001, '0xhash1'), (1002, '0xhash2'), (1003, '0xhash3'), (1004, '0xhash4')]


# -----------------------------
# Tests for EventFetcher asynchronous methods
# -----------------------------
@pytest.mark.asyncio
async def test_get_block_events_success():
    # Create a fake substrate interface for testing.
    fake_substrate = MagicMock()
    # Simulate _preprocess to return an object with the necessary attributes.
    fake_preprocessed = MagicMock()
    fake_preprocessed.method = "dummy_method"
    fake_preprocessed.params = ["dummy_param"]
    fake_preprocessed.value_scale_type = "dummy_scale"
    fake_preprocessed.storage_item = "dummy_item"
    fake_substrate._preprocess = AsyncMock(return_value=fake_preprocessed)

    # make_payload returns a payload string based on the block hash.
    fake_substrate.make_payload = MagicMock(
        side_effect=lambda block_hash, method, params: f"payload_{block_hash}"
    )

    # Prepare a list of (block_number, block_hash) tuples.
    block_info = [(100, "abc"), (101, "def")]

    # Simulate _make_rpc_request to return a dict mapping payloads to event responses.
    def fake_make_rpc_request(payloads, value_scale_type, storage_item):
        return {block_info: [f"event_for_{block_info}"] for block_num, block_info in block_info}

    fake_substrate._make_rpc_request = AsyncMock(
        side_effect=lambda payloads, value_scale_type, storage_item: fake_make_rpc_request(
            payloads, value_scale_type, storage_item
        )
    )

    event_fetcher = EventFetcher()
    events = await event_fetcher.get_block_events(fake_substrate, block_info, max_concurrent=2)

    # Check that the events are mapped correctly.
    assert events[100] == "event_for_abc"
    assert events[101] == "event_for_def"


@pytest.mark.asyncio
async def test_get_block_events_failure():
    # In this test, simulate _preprocess returning an Exception.
    fake_substrate = MagicMock()
    fake_substrate._preprocess = AsyncMock(side_effect=lambda *args, **kwargs: Exception("fail"))
    fake_substrate.make_payload = MagicMock(return_value="dummy_payload")
    fake_substrate._make_rpc_request = AsyncMock(return_value={})

    block_info = [(100, "abc")]
    event_fetcher = EventFetcher()

    with pytest.raises(Exception) as excinfo:
        await event_fetcher.get_block_events(fake_substrate, block_info)
    # Verify that the exception message contains "Preprocessing failed".
    assert "Preprocessing failed" in str(excinfo.value)


# -----------------------------------------------------------
# Test: Empty input list should return an empty dictionary.
# -----------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_all_events_empty():
    event_fetcher = EventFetcher()
    # Create a dummy substrate for group 1 so that get_block is callable.
    fake_substrate1 = MagicMock()
    fake_substrate1.get_block_hash = AsyncMock(return_value="dummy_hash")
    fake_substrate1.get_block = AsyncMock(return_value={'header': {'number': 6000000}})
    event_fetcher.substrates = {1: fake_substrate1}

    # Calling with an empty list.
    result = await event_fetcher.fetch_all_events([])
    assert result == {}


# -----------------------------------------------------------
# Test: Non-integer values in the block_numbers list.
# -----------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_all_events_non_integer():
    event_fetcher = EventFetcher()
    fake_substrate1 = MagicMock()
    fake_substrate1.get_block_hash = AsyncMock(return_value="dummy_hash")
    fake_substrate1.get_block = AsyncMock(return_value={'header': {'number': 6000000}})
    event_fetcher.substrates = {1: fake_substrate1}

    # Provide a list with a non-integer value.
    result = await event_fetcher.fetch_all_events([3014341, "not_an_int", 3804341])
    assert result == {}


# -----------------------------------------------------------
# Test: Normal operation (valid integers with duplicates).
# -----------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_all_events_normal():
    event_fetcher = EventFetcher()

    # Create a fake substrate for group 1 that will be used to get block hashes and the current block.
    fake_substrate1 = MagicMock()
    fake_substrate1.get_block_hash = AsyncMock(side_effect=lambda n: f"hash_{n}")

    # Create dummy substrates for groups 2 to 6.
    fake_substrate2 = MagicMock()
    fake_substrate3 = MagicMock()
    fake_substrate4 = MagicMock()
    fake_substrate5 = MagicMock()
    fake_substrate6 = MagicMock()
    fake_substrate6.get_block = AsyncMock(return_value={'header': {'number': 6000000}})

    # Patch get_block_events to simulate event fetching.
    async def fake_get_block_events(substrate, block_info, max_concurrent=10):
        # For each tuple (block_number, block_hash), return an event string.
        return {block: f"event_for_{block}" for block, _ in block_info}
    event_fetcher.get_block_events = fake_get_block_events

    event_fetcher.substrates = {
        1: fake_substrate1,
        2: fake_substrate2,
        3: fake_substrate3,
        4: fake_substrate4,
        5: fake_substrate5,
        6: fake_substrate6,
    }

    block_numbers = [3014341, 3804341, 4264341, 4920351, 5163657, 5228684, 3014341]  # duplicate 3014341

    # Call the method.
    events = await event_fetcher.fetch_all_events(block_numbers)

    # Expectation: duplicates are removed.
    # The expected events mapping based on groupings and our fake_get_block_events.
    expected_events = {
        3014341: "event_for_3014341",
        3804341: "event_for_3804341",
        4264341: "event_for_4264341",
        4920351: "event_for_4920351",
        5163657: "event_for_5163657",
        5228684: "event_for_5228684",
    }
    assert events == expected_events