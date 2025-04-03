import pytest
import random
from unittest.mock import AsyncMock, patch
from patrol.validation.target_generation import generate_targets, generate_random_block_tuples, find_targets

@pytest.mark.asyncio
async def test_generate_random_block_tuples():
    mock_substrate = AsyncMock()
    with patch("patrol.validation.target_generation.get_current_block", new=AsyncMock(return_value=3_500_000)):
        blocks = await generate_random_block_tuples(mock_substrate, num_targets=2)
        assert len(blocks) == 8
        assert all(isinstance(b, int) for b in blocks)

@pytest.mark.asyncio
async def test_find_targets_basic():
    sample_events = [
        {"coldkey_source": "A", "evidence": {"block_number": 100}},
        {"coldkey_destination": "B", "evidence": {"block_number": 101}},
        {"coldkey_owner": "C", "evidence": {"block_number": 102}},
    ]
    result = await find_targets(sample_events, 2)
    assert len(result) == 2
    assert all(isinstance(x, tuple) and len(x) == 2 for x in result)

@pytest.mark.asyncio
async def test_generate_targets_pads_to_num_targets():
    mock_substrate = AsyncMock()
    mock_fetcher = AsyncMock()
    mock_fetcher.fetch_all_events.return_value = [{"coldkey_source": "A", "evidence": {"block_number": 100}}]
    mock_coldkey_finder = AsyncMock()
    
    with patch("patrol.validation.target_generation.get_current_block", new=AsyncMock(return_value=3_500_000)), \
         patch("patrol.validation.target_generation.process_event_data", new=AsyncMock(return_value=mock_fetcher.fetch_all_events.return_value)):
        
        results = await generate_targets(mock_substrate, mock_fetcher, mock_coldkey_finder, num_targets=3)
        assert len(results) == 3
        assert all(isinstance(t, tuple) for t in results)