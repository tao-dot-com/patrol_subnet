import pytest
import random
from unittest.mock import AsyncMock, patch
from patrol.validation.target_generation import TargetGenerator

@pytest.mark.asyncio
async def test_generate_random_block_tuples():
    fetcher = AsyncMock()
    fetcher.get_current_block.return_value = 3_500_000
    generator = TargetGenerator(fetcher, AsyncMock())

    result = await generator.generate_random_block_tuples(num_targets=2)
    assert len(result) == 8
    assert all(isinstance(n, int) for n in result)

@pytest.mark.asyncio
async def test_find_targets_with_valid_and_invalid():
    generator = TargetGenerator(AsyncMock(), AsyncMock())
    events = [
        {"coldkey_source": "A", "evidence": {"block_number": 1}},
        {"coldkey_destination": "B", "evidence": {"block_number": 2}},
        {"coldkey_owner": "C", "evidence": {"block_number": 3}},
        "invalid_string_event",  # should be skipped
        12345  # also skipped
    ]
    results = await generator.find_targets(events, number_targets=2)
    assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
    assert len(results) <= 2

@pytest.mark.asyncio
async def test_generate_targets_handles_padding():
    fetcher = AsyncMock()
    fetcher.get_current_block.return_value = 3_500_000
    fetcher.fetch_all_events.return_value = {"123": [{"coldkey_source": "X", "evidence": {"block_number": 123}}]}

    with patch("patrol.validation.target_generation.process_event_data", new=AsyncMock(return_value=[
        {"coldkey_source": "X", "evidence": {"block_number": 123}}
    ])):
        generator = TargetGenerator(fetcher, AsyncMock())
        targets = await generator.generate_targets(num_targets=3)

    assert len(targets) == 3
    assert all(isinstance(t, tuple) for t in targets)