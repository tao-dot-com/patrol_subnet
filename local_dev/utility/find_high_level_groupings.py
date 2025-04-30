import asyncio
import json
import time
import os
from tqdm import tqdm 

from async_substrate_interface import AsyncSubstrateInterface

ARCHIVE_NODE_ADDRESS = "wss://archive.chain.opentensor.ai:443/"
ARCHIVE_NODE_ADDRESS = "wss://archive.chain.opentensor.ai:443/"
START_BLOCK = 5280452
END_BLOCK = 5413791
BLOCK_STEP = 1000

# Total number of block samples we will process:
TOTAL_BLOCKS_TO_PROCESS = (END_BLOCK - START_BLOCK) / BLOCK_STEP

async def return_block_version(substrate, block_number, semaphore):
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
    blocks_processed = (block_number - START_BLOCK) / BLOCK_STEP
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
        hash_tasks = [return_block_version(substrate, bn, semaphore) for bn in block_numbers]
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

async def main():

    # Gather block info from the chain.
    results = await gather_block_info(START_BLOCK, END_BLOCK, BLOCK_STEP)

    # Save raw block info to JSON file.
    raw_output_file = "block_info.json"
    with open(raw_output_file, "w") as f:
        json.dump(results, f, indent=4)
    print(f"Block info saved to {raw_output_file}")

    # Compute runtime version ranges.
    runtime_ranges = compute_runtime_ranges(results)
    
    # Save runtime ranges to a separate JSON file.
    ranges_output_file = "runtime_ranges.json"
    with open(ranges_output_file, "w") as f:
        json.dump(runtime_ranges, f, indent=4)
    print(f"Runtime version ranges saved to {ranges_output_file}")

if __name__ == "__main__":
    asyncio.run(main())