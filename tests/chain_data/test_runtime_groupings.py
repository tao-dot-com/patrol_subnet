import pytest
from unittest.mock import patch

from patrol.chain_data.runtime_groupings import get_version_for_block, group_blocks, VersionData

# Sample test version data
TEST_VERSIONS: VersionData = {
    "1": {"block_number_min": 100, "block_number_max": 199},
    "2": {"block_number_min": 200, "block_number_max": 299},
    "3": {"block_number_min": 300, "block_number_max": 399},
}

@pytest.mark.parametrize("block_number, current_block, expected", [
    (100, 500, 1),     # exact lower bound
    (150, 500, 1),     # within range
    (299, 500, 2),     # exact upper bound of version 2
    (350, 500, 3),     # inside highest range
    (400, 500, 3),     # above highest max, returns highest version
    (50,  500, None),  # below all ranges
    (999, 800, None),  # above current block height
])
def test_get_version_for_block(block_number: int, current_block: int, expected: int):
    result = get_version_for_block(block_number, current_block, TEST_VERSIONS)
    assert result == expected

def test_group_blocks_basic():
    block_numbers = [110, 220, 230, 310, 320]
    block_hashes = [f"hash_{b}" for b in block_numbers]
    current_block = 500
    batch_size = 2

    result = group_blocks(block_numbers, block_hashes, current_block, TEST_VERSIONS, batch_size)

    # Group 1 should have 1 block
    assert 1 in result
    assert result[1] == [[(110, "hash_110")]]

    # Group 2 should have 2 blocks batched into 1
    assert 2 in result
    assert result[2] == [[(220, "hash_220"), (230, "hash_230")]]

    # Group 3 should have 2 blocks batched into 1
    assert 3 in result
    assert result[3] == [[(310, "hash_310"), (320, "hash_320")]]


@patch("bittensor.logging.warning")
def test_group_blocks_with_out_of_range_blocks(mock_warning):
    block_numbers = [90, 150, 999]
    block_hashes = [f"hash_{b}" for b in block_numbers]
    current_block = 800

    result = group_blocks(block_numbers, block_hashes, current_block, TEST_VERSIONS, batch_size=10)

    # Only 150 should be grouped
    assert result == {1: [[(150, "hash_150")]]}

    # Ensure warning was called twice (for 90 and 999)
    assert mock_warning.call_count == 2