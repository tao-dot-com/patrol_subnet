import pytest
import random
from unittest.mock import AsyncMock, patch
from patrol.validation.target_generation import TargetGenerator

# Fixture to simulate the event_fetcher dependency.
@pytest.fixture
def dummy_event_fetcher():
    fetcher = AsyncMock()
    # Return a current block that is high enough for generate_random_block_tuples.
    fetcher.get_current_block.return_value = 3_100_000
    return fetcher

# Fixture to simulate the event_processor dependency.
@pytest.fixture
def dummy_event_processor():
    processor = AsyncMock()
    return processor

# Fixture for the TargetGenerator instance.
@pytest.fixture
def target_generator(dummy_event_fetcher, dummy_event_processor):
    return TargetGenerator(dummy_event_fetcher, dummy_event_processor)

# ---------------------------
# Test generate_random_block_tuples
# ---------------------------

@pytest.mark.asyncio
async def test_generate_random_block_tuples_deterministic(target_generator, monkeypatch):
    # Patch random.randint to always return the lower bound (for a predictable start_block).
    monkeypatch.setattr(random, "randint", lambda a, b: a)
    num_targets = 1
    blocks = await target_generator.generate_random_block_tuples(num_targets)
    # Expected: 4 block numbers starting at 3_014_342 and increasing by 500.
    expected = [3_014_342 + i * 500 for i in range(num_targets * 4)]
    assert blocks == expected

@pytest.mark.asyncio
async def test_generate_random_block_tuples_progression(target_generator):
    num_targets = 2
    blocks = await target_generator.generate_random_block_tuples(num_targets)
    # Should return num_targets * 4 block numbers (here, 8).
    assert isinstance(blocks, list)
    assert len(blocks) == num_targets * 4
    # Verify that each subsequent block number increases by 500.
    for i in range(1, len(blocks)):
        assert blocks[i] - blocks[i - 1] == 500

# ---------------------------
# Test find_targets
# ---------------------------

@pytest.mark.asyncio
async def test_find_targets(target_generator):
    # Prepare a list of events with various valid and invalid cases.
    events = [
        {"evidence": {"block_number": 100}, "coldkey_source": "A"},
        {"evidence": {"block_number": 100}, "coldkey_destination": "B"},
        {"evidence": {"block_number": 200}, "coldkey_owner": "C"},
        "not a dict",  # should be ignored
        {"evidence": {"block_number": None}, "coldkey_source": "D"},  # invalid block number
        {"coldkey_source": "E"}  # missing evidence
    ]
    # Request 2 target tuples.
    targets = await target_generator.find_targets(events, 2)
    # The valid unique targets extracted should be:
    expected_set = {("A", 100), ("B", 100), ("C", 200)}
    # Each returned tuple should belong to the expected set.
    for target in targets:
        assert target in expected_set
    # The number of targets returned should be the minimum of requested or available.
    assert len(targets) == 2

# ---------------------------
# Test generate_targets (integration)
# ---------------------------

@pytest.mark.asyncio
async def test_generate_targets_success(target_generator, dummy_event_fetcher, dummy_event_processor):
    num_targets = 2
    # Simulate fetch_all_events returning a dictionary keyed by block numbers.
    fake_events = {
        3100000: [
            {"evidence": {"block_number": 100}, "coldkey_source": "A"},
            {"evidence": {"block_number": 100}, "coldkey_destination": "B"},
            {"evidence": {"block_number": 200}, "coldkey_owner": "C"}
        ]
    }
    dummy_event_fetcher.fetch_all_events.return_value = fake_events
    # Simulate process_event_data returning a list of events.
    dummy_event_processor.process_event_data.return_value = [
        {"evidence": {"block_number": 100}, "coldkey_source": "A"},
        {"evidence": {"block_number": 100}, "coldkey_destination": "B"},
        {"evidence": {"block_number": 200}, "coldkey_owner": "C"}
    ]
    targets = await target_generator.generate_targets(num_targets)
    # Verify that the returned targets list has the desired length.
    assert isinstance(targets, list)
    assert len(targets) == num_targets
    # Each target should be a tuple containing an address and a block number.
    for target in targets:
        assert isinstance(target, tuple)
        assert len(target) == 2

@pytest.mark.asyncio
async def test_generate_targets_no_targets(target_generator, dummy_event_fetcher, dummy_event_processor):
    num_targets = 2
    # Simulate a scenario where no on-chain events are returned.
    fake_events = {3100000: []}
    dummy_event_fetcher.fetch_all_events.return_value = fake_events
    dummy_event_processor.process_event_data.return_value = []
    targets = await target_generator.generate_targets(num_targets)
    # If no targets are found, generate_targets should return an empty list.
    assert targets == []