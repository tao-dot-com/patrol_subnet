import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# Define type aliases for clarity
VersionRange = Dict[str, int]
VersionData = Dict[str, VersionRange]

# Load JSON from file
def load_versions(filename: str = "runtime_versions.json") -> VersionData:
    # Get the path to the current file and ensure relative to it
    here = Path(__file__).parent.resolve()
    filepath = here / filename

    with open(filepath, 'r') as f:
        return json.load(f)

# Create a function to get the version for a block number
def get_version_for_block(
    block_number: int,
    current_block: int,
    versions: VersionData
) -> Optional[int]:
    # Convert version keys to integers for sorting
    version_bounds: Dict[int, VersionRange] = {int(v): b for v, b in versions.items()}

    # Find the version with the lowest 'min' and highest 'max'
    min_bound_version = min(version_bounds.items(), key=lambda x: x[1]['block_number_min'])
    max_bound_version = max(version_bounds.items(), key=lambda x: x[1]['block_number_max'])

    lowest_min = min_bound_version[1]['block_number_min']
    highest_version = max_bound_version[0]
    highest_max = max_bound_version[1]['block_number_max']

    # If block is below all known ranges
    if block_number < lowest_min:
        return None

    # If block is within any known range
    for version, bounds in version_bounds.items():
        if bounds['block_number_min'] <= block_number <= bounds['block_number_max']:
            return version

    # If block is beyond current block height, it's not yet valid
    if block_number > current_block:
        return None

    # If block is above highest known max, return that highest version
    if block_number > highest_max:
        return highest_version

    return None  # Should not reach here

def group_blocks(
    block_numbers: List[int],
    block_hashes: List[str],
    current_block: int,
    versions: VersionData,
    batch_size: int = 25
) -> Dict[int, List[List[int]]]:
    """
    Groups blocks by version and splits each group into batches.

    Args:
        block_numbers: List of block numbers.
        current_block: Current latest block.
        versions: Version boundaries for blocks.
        batch_size: Maximum number of blocks per batch (default 25).

    Returns:
        Dictionary mapping version number to list of block batches (each a list of ints).
    """
    grouped: Dict[int, List[int]] = {}
    for block_number, block_hash in zip(block_numbers, block_hashes):
        group = get_version_for_block(block_number, current_block, versions)
        if group is not None:
            grouped.setdefault(group, []).append((block_number, block_hash))
        else:
            logger.warning(f"Block {block_number} is outside current groupings.")

    batched: Dict[int, List[List[int]]] = {}
    for group_id, block_list in grouped.items():
        batched[group_id] = [
            block_list[i:i + batch_size] for i in range(0, len(block_list), batch_size)
        ]

    return batched

# Example usage
if __name__ == "__main__":
    versions = load_versions()  # Replace with your actual file name
    print(versions)
    block_numbers = [5400000]
    block_hashes = ["test"]
    current_block = 5400001
    groupings = group_blocks(block_numbers, block_hashes, current_block, versions)
    print(groupings)