import asyncio
from typing import Dict, List, Tuple, Any
import pytest
from unittest.mock import AsyncMock, MagicMock
import bittensor as bt

from patrol.chain_data.event_fetcher import EventFetcher

# ----------------------------
# Tests for EventFetcher methods
# ----------------------------

@pytest.mark.asyncio
async def test_get_current_block():
    # Arrange: fake substrate_client returns a block with header number.
    fake_block = {"header": {"number": 5000000}}
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(return_value=fake_block)
    
    ef = EventFetcher(fake_substrate_client)
    
    # Act
    block_num = await ef.get_current_block()
    
    # Assert
    assert block_num == 5000000
    fake_substrate_client.query.assert_awaited_once_with("get_block", None)

class FakePreprocessed:
    def __init__(self):
        self.method = "dummy_method"
        self.params = ["param0"]
        self.value_scale_type = "scale"
        self.storage_item = "item"

@pytest.mark.asyncio
async def test_get_block_events_success():
    # Arrange: two blocks to process.
    block_info: List[Tuple[int, str]] = [(100, "hash100"), (101, "hash101")]
    
    # Fake preprocessed response.
    fake_preprocessed = FakePreprocessed()
    
    async def fake_query(method_name, version, *args, **kwargs):
        if method_name == "_preprocess":
            return fake_preprocessed
        elif method_name == "_make_rpc_request":
            # Build a fake response mapping:
            response = {}
            for arg in args[0]:
                key = arg['id']
                response[key] = [f"event_for_{key}"]
            return response
        else:
            return None

    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=fake_query)
    
    ef = EventFetcher(fake_substrate_client)
    
    # Act
    events = await ef.get_block_events(None, block_info, max_concurrent=2)
    
    # Assert: Expect a mapping from block number to the corresponding fake event.
    expected: Dict[int, Any] = {100: "event_for_hash100", 101: "event_for_hash101"}
    assert events == expected

@pytest.mark.asyncio
async def test_get_block_events_preprocess_failure():
    # Arrange: simulate failure in _preprocess.
    block_info: List[Tuple[int, str]] = [(100, "hash100")]
    
    async def fake_query(method_name, version, *args, **kwargs):
        if method_name == "_preprocess":
            raise Exception("Preprocess failure")
        elif method_name == "_make_rpc_request":
            return {}
    
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=fake_query)
    
    ef = EventFetcher(fake_substrate_client)
    
    # Act & Assert: Expect an exception when preprocessing fails.
    with pytest.raises(Exception) as excinfo:
        await ef.get_block_events(1, block_info)
    assert "Preprocess failure" in str(excinfo.value)

@pytest.mark.asyncio
async def test_fetch_all_events_empty_and_invalid_input():
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(return_value={"header": {"number": 5000000}})
    ef = EventFetcher(fake_substrate_client)
    
    # Act & Assert for empty input.
    events = await ef.fetch_all_events([])
    assert events == {}
    
    # Act & Assert for non-integer input.
    events = await ef.fetch_all_events(["not_an_int", 123])
    assert events == {}

@pytest.mark.asyncio
async def test_fetch_all_events_success(monkeypatch):
    block_numbers = [3100000, 3200000]
    fake_events = {
        3100000: "event_3100000",
        3200000: "event_3200000"
    }

    # Mock substrate client and return_runtime_versions
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=lambda method, _, n=None: {
        "get_block_hash": f"hash{n}",
        "get_block": {"header": {"number": 6000000}}
    }[method])
    fake_substrate_client.return_runtime_versions = MagicMock(return_value={6: "version6"})

    # Create fetcher
    ef = EventFetcher(fake_substrate_client)

    # Patch group_blocks
    def fake_group_blocks(block_numbers, block_hashes, current_block, versions, batch_size):
        return {6: [[(n, f"hash{n}") for n in block_numbers]]}
    monkeypatch.setattr("patrol.chain_data.event_fetcher.group_blocks", fake_group_blocks)

    # Patch get_block_events to return fake events
    ef.get_block_events = AsyncMock(return_value=fake_events)

    # Run fetch_all_events
    result = await ef.fetch_all_events(block_numbers)

    assert result == fake_events
    ef.get_block_events.assert_called_once()

@pytest.mark.asyncio
async def test_stream_all_events_empty_input():
    ef = EventFetcher(MagicMock())
    ef.hash_semaphore = asyncio.Semaphore(1)
    ef.event_semaphore = asyncio.Semaphore(1)
    
    queue = asyncio.Queue()
    await ef.stream_all_events([], queue)
    
    result = await queue.get()
    assert result is None

@pytest.mark.asyncio
async def test_stream_all_events_invalid_input():
    ef = EventFetcher(MagicMock())
    ef.hash_semaphore = asyncio.Semaphore(1)
    ef.event_semaphore = asyncio.Semaphore(1)

    queue = asyncio.Queue()
    await ef.stream_all_events(["abc", 123], queue)
    
    result = await queue.get()
    assert result is None

@pytest.mark.asyncio
async def test_stream_all_events_success(monkeypatch):
    block_numbers = [100, 101, 102]
    block_hashes = [f"hash{n}" for n in block_numbers]
    fake_events = {n: f"event_for_{n}" for n in block_numbers}

    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=lambda method, _, n=None: f"hash{n}" if method == "get_block_hash" else {"header": {"number": 9999}})
    fake_substrate_client.return_runtime_versions = MagicMock(return_value={1: "version1"})

    ef = EventFetcher(fake_substrate_client)
    ef.hash_semaphore = asyncio.Semaphore(10)
    ef.event_semaphore = asyncio.Semaphore(10)
    ef.get_current_block = AsyncMock(return_value=9999)
    ef.get_block_events = AsyncMock(side_effect=lambda version, batch: {n: f"event_for_{n}" for n, _ in batch})

    def fake_group_blocks(block_nums, hashes, current_block, versions, batch_size):
        return {1: [[(n, f"hash{n}") for n in block_nums]]}

    monkeypatch.setattr("patrol.chain_data.event_fetcher.group_blocks", fake_group_blocks)

    queue = asyncio.Queue()
    await ef.stream_all_events(block_numbers, queue)

    results = []
    while True:
        batch = await queue.get()
        if batch is None:
            break
        results.append(batch)

    assert len(results) == 1
    assert results[0] == fake_events

@pytest.mark.asyncio
async def test_stream_all_events_handles_batch_failure(monkeypatch):
    block_numbers = [100, 101]
    block_hashes = [f"hash{n}" for n in block_numbers]

    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=lambda method, _, n=None: f"hash{n}" if method == "get_block_hash" else {"header": {"number": 9999}})
    fake_substrate_client.return_runtime_versions = MagicMock(return_value={1: "version1"})

    ef = EventFetcher(fake_substrate_client)
    ef.hash_semaphore = asyncio.Semaphore(10)
    ef.event_semaphore = asyncio.Semaphore(10)
    ef.get_current_block = AsyncMock(return_value=9999)
    ef.get_block_events = AsyncMock(side_effect=Exception("Boom"))

    def fake_group_blocks(block_nums, hashes, current_block, versions, batch_size):
        return {1: [[(n, f"hash{n}") for n in block_nums]]}

    monkeypatch.setattr("patrol.chain_data.event_fetcher.group_blocks", fake_group_blocks)

    queue = asyncio.Queue()
    await ef.stream_all_events(block_numbers, queue)

    result = await queue.get()
    assert result is None