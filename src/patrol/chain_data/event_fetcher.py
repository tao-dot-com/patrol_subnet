import asyncio
import logging
import time
from typing import Dict, Iterable, List, Tuple, Any

from async_substrate_interface import AsyncSubstrateInterface
from patrol.chain_data.runtime_groupings import group_blocks

logger = logging.getLogger(__name__)

class EventFetcher:
    def __init__(self, substrate_client):
        self.substrate_client = substrate_client
        self.hash_semaphore = asyncio.Semaphore(20)
        self.event_semaphore = asyncio.Semaphore(1)
  
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

        if not block_numbers:
            logger.warning("No block numbers provided. Returning empty event dictionary.")
            return {}
        
        if any(not isinstance(b, int) for b in block_numbers):
            logger.warning("Non-integer value found in block_numbers. Returning empty event dictionary.")
            return {}

        block_numbers = set(block_numbers)

        async with self.event_semaphore:
            logger.info(f"Attempting to fetch event data for {len(block_numbers)} blocks...")

            block_hash_tasks = [
                self.substrate_client.query("get_block_hash", None, n)
                for n in block_numbers
            ]
            block_hashes = await asyncio.gather(*block_hash_tasks)

            current_block = await self.get_current_block()

            versions = self.substrate_client.return_runtime_versions()
            grouped = group_blocks(block_numbers, block_hashes, current_block, versions, batch_size)

            all_events: Dict[int, Any] = {}
            for runtime_version, batches in grouped.items():
                for batch in batches:
                    logger.info(f"Fetching events for runtime version {runtime_version} (batch of {len(batch)} blocks)...")
                    try:
                        events = await self.get_block_events(runtime_version, batch)
                        logger.info(f"Successfully fetched events for runtime version {runtime_version}. Updating...")
                        all_events.update(events)
                        logger.info(f"Updated events for runtime version {runtime_version}.")
                    except Exception as e:
                        logger.warning(
                            f"Unable to fetch events for runtime version {runtime_version} batch on final attempt: {e}. Continuing..."
                        )
        # Continue to next version even if the current one fails.
        logger.info(f"All events collected in {time.time() - start_time} seconds.")
        return all_events

    async def stream_all_events(
        self,
        block_numbers: Iterable[int],
        queue: asyncio.Queue,
        batch_size: int = 25,
    ) -> None:
        """
        Streams events into a queue. Each batch of events is put into the queue as it's fetched.
        """
        if not block_numbers:
            logger.warning("No block numbers provided. Nothing to yield.")
            await queue.put(None)
            return

        if any(not isinstance(b, int) for b in block_numbers):
            logger.warning("Non-integer value found in block_numbers. Nothing to yield.")
            await queue.put(None)
            return

        block_numbers = set(block_numbers)
        logger.info(f"Attempting to stream event data for {len(block_numbers)} blocks...")

        async def safe_get_block_hash(n: int) -> str | None:
            try:
                async with self.hash_semaphore:
                    return await self.substrate_client.query("get_block_hash", None, n)
            except Exception as e:
                logger.warning(f"Failed to retrieve block hash for block {n}: {e}")
                return None

        block_hashes = await asyncio.gather(*[safe_get_block_hash(n) for n in block_numbers])
        current_block = await self.get_current_block()
        versions = self.substrate_client.return_runtime_versions()
        grouped = group_blocks(block_numbers, block_hashes, current_block, versions, batch_size)

        async def fetch_and_return_events(runtime_version, batch, timeout=2):
            async with self.event_semaphore:
                try:
                    logger.debug(f"Fetching events for runtime version {runtime_version} (batch of {len(batch)} blocks)...")
                    events = await asyncio.wait_for(
                        self.get_block_events(runtime_version, batch),
                        timeout=timeout
                    )
                    logger.debug(f"Yielding {len(events)} events from batch.")
                    if events is not None:
                        await queue.put(events)
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout while fetching events for runtime version {runtime_version}, batch of size {len(batch)}")
                except Exception as e:
                    logger.warning(f"Skipping failed batch due to error: {e}")

        # Launch all batch tasks
        tasks = [
            fetch_and_return_events(runtime_version, batch)
            for runtime_version, batches in grouped.items()
            for batch in batches
        ]
        await asyncio.gather(*tasks)

        await queue.put(None)
            
async def example():

    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions

    network_url = "wss://archive.chain.opentensor.ai:443/"
    versions = load_versions()
    
    keys_to_keep = {"257"}
    versions = {k: versions[k] for k in keys_to_keep if k in versions}
    
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    await client.initialize()

    fetcher = EventFetcher(substrate_client=client)

    test_cases = [
        # [3014340 + i for i in range(1000)],
        [5255099 + i for i in range(1000)]
        # [3804341 + i for i in range(1000)]    # high volume
    ]

    for test_case in test_cases:

        logger.info("Starting next test case.")

        start_time = time.time()
        all_events = []
        async for events in fetcher.stream_all_events(
                test_case,
                25
            ): 
            all_events.extend(events)

        print(f"Retrieved events for {len(all_events)} blocks in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(example())
