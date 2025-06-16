import asyncio
import json
import time
import os
from tqdm import tqdm 

from async_substrate_interface import AsyncSubstrateInterface

ARCHIVE_NODE_ADDRESS = "wss://archive.chain.opentensor.ai:443/"
ARCHIVE_NODE_ADDRESS = "wss://archive.chain.opentensor.ai:443/"

# Total number of block samples we will process:
TOTAL_BLOCKS_TO_PROCESS = 1000

async def return_block_version(substrate, start_block, block_number, semaphore):
    """
    Given a substrate interface, a block number, and a semaphore to limit concurrency,
    retrieves the block hash and then the runtime version for that block.
    Prints progress information based on the processing time.
    """
    async with semaphore:
        start_time = time.time()
        # Retrieve the block hash for the block number
        block_hash = await substrate.get_block_hash(block_id=block_number)
        # Retrieve the runtime version for the block hash
        version = await substrate.get_block_runtime_version_for(block_hash)
    
    elapsed_time = time.time() - start_time

    # Compute progress based on our current block number
    blocks_processed = (block_number - start_block)
    blocks_remaining = TOTAL_BLOCKS_TO_PROCESS - blocks_processed
    progress_fraction = blocks_processed / TOTAL_BLOCKS_TO_PROCESS

    # Estimate remaining time using the elapsed time for this block (this is a rough estimate)
    estimated_time_remaining = blocks_remaining * elapsed_time

    # Print the progress information in a nicely formatted way:
    print(
        f"Progress: {progress_fraction:.5f} | "
        f"Estimated time remaining: {estimated_time_remaining:.2f} sec"
    )

    return version

async def gather_block_info(start_block: int, end_block: int, step: int):
    async with AsyncSubstrateInterface(url=ARCHIVE_NODE_ADDRESS) as substrate:
        # Get current block number (assuming the returned number is a string or int)
        
        # Create a list of block numbers to sample
        block_numbers = list(range(start_block, end_block, step))
        print(f"Fetching block hashes for {len(block_numbers)} blocks...")

        semaphore = asyncio.Semaphore(5)
        
        # Get block hashes concurrently
        hash_tasks = [return_block_version(substrate, start_block, bn, semaphore) for bn in block_numbers]
        versions = await asyncio.gather(*hash_tasks)

        # Assemble results as a list of dictionaries.
        results = []
        for bn, version in zip(block_numbers, versions):
            print(f"Block: {bn}   Runtime Version: {version}")
            results.append({
                "block_number": bn,
                "runtime_version": str(version)
            })
    return results

def compute_runtime_ranges(results):
    """
    Given a list of block info dictionaries (each with 'block_number' and 'runtime_version'),
    compute the min and max block number for each runtime version.
    """
    runtime_ranges = {}
    for entry in results:
        rt = entry["runtime_version"]
        bn = entry["block_number"]
        if rt in runtime_ranges:
            runtime_ranges[rt]["min"] = min(runtime_ranges[rt]["min"], bn)
            runtime_ranges[rt]["max"] = max(runtime_ranges[rt]["max"], bn)
        else:
            runtime_ranges[rt] = {"min": bn, "max": bn}
    return runtime_ranges

def load_runtime_ranges(filename="runtime_ranges.json"):
    """
    Loads runtime ranges from a JSON file.
    Expected format is a JSON object where keys are runtime versions (as strings)
    and each value is a dictionary with "min" and "max" block numbers.
    """
    with open(filename, "r") as f:
        ranges = json.load(f)
    # Convert to a list of tuples: (runtime_version as int, min, max)
    sorted_ranges = sorted(
        ((int(rt), data["min"], data["max"]) for rt, data in ranges.items()),
        key=lambda x: x[1]
    )
    return sorted_ranges

async def main():

    provided_ranges = load_runtime_ranges("high_level_runtime_ranges.json")

    for i in range(1, len(provided_ranges)):
        print(f"Finding range for: {provided_ranges[i-1][2]}-{provided_ranges[i][1]}")

        # Gather block info from the chain.
        results = await gather_block_info(provided_ranges[i-1][2], provided_ranges[i][1], 1)

        # Save raw block info to JSON file.
        raw_output_file = "block_info.json"
        with open(raw_output_file, "w") as f:
            json.dump(results, f, indent=4)
        print(f"Block info saved to {raw_output_file}")

        # Compute runtime version ranges.
        runtime_ranges = compute_runtime_ranges(results)
        
        # Save runtime ranges to a separate JSON file.
        ranges_output_file = f"runtime_ranges_{provided_ranges[i-1][2]}-{provided_ranges[i][1]}.json"
        with open(ranges_output_file, "w") as f:
            json.dump(runtime_ranges, f, indent=4)
        print(f"Runtime version ranges saved to {ranges_output_file}")

if __name__ == "__main__":
    asyncio.run(main())