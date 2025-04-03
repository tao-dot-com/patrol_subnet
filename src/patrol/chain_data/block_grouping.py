from bittensor import AsyncSubtensor
from async_substrate_interface import AsyncSubstrateInterface

from patrol.constants import Constants

import time
import asyncio

import json
import time
import os

async def test_runtime_compatibility(block_tuples, output_path="runtime_compatibility.jsonl"):
    import os
    if os.path.exists(output_path):
        os.remove(output_path)

    async with AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS) as substrate:
        total = len(block_tuples)
        for i, (init_num, init_hash, init_ver) in enumerate(block_tuples):
            print(f"\n[{i+1}/{total}] Initializing runtime with block {init_num} (v{init_ver})...")
            await substrate.init_runtime(block_hash=init_hash)
            row = {}
            for j, (test_num, test_hash, test_ver) in enumerate(block_tuples):
                print(f"  - Testing compatibility with block {test_num} (v{test_ver})...")

                for attempt in range(3):
                    try:
                        preprocessed_hash = await substrate._preprocess(
                            None, test_hash, module="System", storage_function="Events"
                        )
                        if isinstance(preprocessed_hash, Exception):
                            raise Exception(f"Preprocessing failed: {preprocessed_hash}")
                        payload = substrate.make_payload(
                            f"{test_hash}",
                            preprocessed_hash.method,
                            [preprocessed_hash.params[0], test_hash]
                        )
                        await asyncio.wait_for(
                            substrate._make_rpc_request(
                                [payload],
                                preprocessed_hash.value_scale_type,
                                preprocessed_hash.storage_item
                            ),
                            timeout=30
                        )
                        row[f"{test_num} (v{test_ver})"] = True
                        break  # Success
                    except Exception as e:
                        if attempt == 2:  # Last retry
                            row[f"{test_num} (v{test_ver})"] = False

            with open(output_path, "a") as f:
                f.write(json.dumps({f"{init_num} (v{init_ver})": row}) + "\n")

    print(f"\n✅ Compatibility results streamed to {output_path}")

async def main():
    async with AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS) as substrate:

        block_numbers = list(range(3014340, 5250736, 10000))

        print("Fetching block hashes...")
        tasks = [substrate.get_block_hash(block_id=block_number) for block_number in block_numbers]
        hashes = await asyncio.gather(*tasks)

        print("Fetching runtime versions...")
        runtime_versions = [substrate.get_block_runtime_version_for(hash) for hash in hashes]
        versions = await asyncio.gather(*runtime_versions)

        block_tuples = list(zip(block_numbers, hashes, versions))

        for num, _, version in block_tuples:
            print(f"Num: {num}   Version: {version}")

        print(f"Starting compatibility test for {len(block_tuples)} blocks...\n")
        start_time = time.time()
        # await test_runtime_compatibility(block_tuples)
        end_time = time.time()
        print(f"\n⏱️ Finished in: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(main())