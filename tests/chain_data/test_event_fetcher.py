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
    # Arrange: use a list of block numbers.
    block_numbers = [3100000, 3200000]

    fake_preprocessed = FakePreprocessed()

    async def fake_query(method_name, version, *args, **kwargs):
        if method_name == "get_block":
            return {"header": {"number": 6000000}}
        if method_name == "_preprocess":
            return fake_preprocessed
        elif method_name == "_make_rpc_request":
            # Build a fake response mapping:
            response = {}
            for arg in args[0]:
                key = arg['id']
                response[key] = [f"fake_event_for_{key}"]
            return response
        else:
            return None

    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(side_effect=fake_query)
    
    # For grouping, override group_blocks to control grouping.
    def fake_group_blocks(block_numbers, block_hashes, current_block, versions, batch_size):
        # Return a single group (say, group 6) with one batch containing all block info.
        return {6: [[(n, f"hash{n}") for n in block_numbers]]}
    
    monkeypatch.setattr("patrol.chain_data.event_fetcher.group_blocks", fake_group_blocks)
    
    ef = EventFetcher(fake_substrate_client)

    events = await ef.fetch_all_events(block_numbers)
    
    # Assert: Expect a mapping from block number to the fake event.
    expected = {3100000: "fake_event_for_hash3100000", 3200000: "fake_event_for_hash3200000"}
    assert events == expected