import asyncio
import logging
import time
from typing import Dict, List, Tuple, Any

import bittensor as bt
from async_substrate_interface import AsyncSubstrateInterface
from patrol.chain_data.runtime_groupings import group_blocks

class EventFetcher:
    def __init__(self, substrate_client):
        self.substrate_client = substrate_client
        self.semaphore = asyncio.Semaphore(1)
  
    async def get_current_block(self) -> int:
        current_block = await self.substrate_client.query("get_block", None)
        return current_block["header"]["number"]

    async def get_block_events(
        self,
        runtime_version: int,
        block_info: List[Tuple[int, str]],
        max_concurrent: int = 10
    ) -> Dict[int, Any]:
        """
        Fetch events for a batch of blocks for a specific runtime_version using the substrate client's query method.
        """
        # Extract block hashes for processing.
        block_hashes = [block_hash for (_, block_hash) in block_info]
        semaphore = asyncio.Semaphore(max_concurrent)

        async def preprocess_with_semaphore(block_hash):
            async with semaphore:
                # Use the query method to call the substrate's _preprocess method.
                return await self.substrate_client.query(
                    "_preprocess",
                    runtime_version,
                    None,
                    block_hash,
                    module="System",
                    storage_function="Events"
                )

        tasks = [preprocess_with_semaphore(h) for h in block_hashes]
        preprocessed_lst = await asyncio.gather(*tasks)
        errors = [r for r in preprocessed_lst if isinstance(r, Exception)]
        if errors:
            raise Exception(f"Preprocessing failed: {errors}")

        payloads = [
            AsyncSubstrateInterface.make_payload(
                str(block_hash),
                preprocessed.method,
                [preprocessed.params[0], block_hash]
            )
            for block_hash, preprocessed in zip(block_hashes, preprocessed_lst)
        ]

        responses = await asyncio.wait_for(
            self.substrate_client.query(
                "_make_rpc_request",
                runtime_version,
                payloads,
                preprocessed_lst[0].value_scale_type,
                preprocessed_lst[0].storage_item
            ),
            timeout=3
        )

        # Build a mapping from block_number to event response.
        return {
            block_number: responses[block_hash][0]
            for (block_number, block_hash) in block_info
        }
    
    async def fetch_all_events(self, block_numbers: List[int], batch_size: int = 25) -> Dict[int, Any]:
        """
        Retrieve events for all given block numbers.
        """
        start_time = time.time()

        # Validate input: check if block_numbers is empty.
        if not block_numbers:
            bt.logging.warning("No block numbers provided. Returning empty event dictionary.")
            return {}

        # Validate that all items in block_numbers are integers.
        if any(not isinstance(b, int) for b in block_numbers):
            bt.logging.warning("Non-integer value found in block_numbers. Returning empty event dictionary.")
            return {}

        # Get rid of duplicates
        block_numbers = set(block_numbers)

        async with self.semaphore:
            bt.logging.info(f"\nAttempting to fetch event data for {len(block_numbers)} blocks...")

            block_hash_tasks = [
                self.substrate_client.query("get_block_hash", None, n)
                for n in block_numbers
            ]
            block_hashes = await asyncio.gather(*block_hash_tasks)

            # Need to make sure we always use the latest substrate to get the current block otherwise it can throw off older substrate
            current_block = await self.get_current_block()

            # Group blocks by group while maintaining the block number alongside its hash.
            versions = self.substrate_client.return_runtime_versions()
            grouped = group_blocks(block_numbers, block_hashes, current_block, versions, batch_size)

            all_events: Dict[int, Any] = {}
            for runtime_version, batches in grouped.items():
                for batch in batches:
                    bt.logging.debug(f"\nFetching events for runtime version {runtime_version} (batch of {len(batch)} blocks)...")
                    try:
                        events = await self.get_block_events(runtime_version, batch)
                        all_events.update(events)
                        bt.logging.debug(f"Successfully fetched events for runtime version {runtime_version} batch.")
                    except Exception as e:
                        bt.logging.debug(
                            f"Unable to fetch events for runtime version {runtime_version} batch on final attempt: {e}. Continuing..."
                        )
            # Continue to next version even if the current one fails.
        bt.logging.debug(f"All events collected in {time.time() - start_time} seconds.")
        return all_events

async def example():

    import json

    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions

    network_url = "wss://archive.chain.opentensor.ai:443/"
    versions = load_versions()
    
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    await client.initialize()

    fetcher = EventFetcher(substrate_client=client)

    test_cases = [
        [5163655 + i for i in range(1000)],
        # [3804341 + i for i in range(1000)]    # high volume
    ]

    for test_case in test_cases:

        bt.logging.info("Starting next test case.")

        start_time = time.time()
        all_events = await fetcher.fetch_all_events(test_case, 50)
        bt.logging.info(f"\nRetrieved events for {len(all_events)} blocks in {time.time() - start_time:.2f} seconds.")

        with open('raw_event_data.json', 'w') as file:
            json.dump(all_events, file, indent=4)

        # bt.logging.debug(all_events)

if __name__ == "__main__":
    asyncio.run(example())