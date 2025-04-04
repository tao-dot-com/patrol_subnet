import asyncio
import time
from typing import Dict, List, Tuple, Any
from async_substrate_interface import AsyncSubstrateInterface
import bittensor as bt

from patrol.constants import Constants

GROUP_INIT_BLOCK = {
    1: 3784340,
    2: 4264340,
    3: 4920350,
    4: 5163656,
    5: 5228683,
    6: 5228685,
}

def group_block(block: int, current_block: int) -> int:
    if block <= 3014340:
        return None
    elif block <= 3804340:
        return 1
    elif block <= 4264340:
        return 2
    elif block <= 4920350:
        return 3
    elif block <= 5163656:
        return 4
    elif block <= 5228684:
        return 5
    elif block > 5228684 and block <= current_block:
        return 6
    return None

def group_blocks(
        block_numbers: List[int], 
        block_hashes: List[str],
        current_block: int
    ) -> Dict[int, List[Tuple[int, str]]]:
        """
        Group blocks by their group id while preserving both block number and hash.
        
        Returns:
            A dictionary mapping group id to a list of tuples (block_number, block_hash).
        """
        grouped: Dict[int, List[Tuple[int, str]]] = {}
        for block_number, block_hash in zip(block_numbers, block_hashes):
            group = group_block(block_number, current_block)
            if group:
                grouped.setdefault(group, []).append((block_number, block_hash))
            else:
                bt.logging.warning(f"Block {block_number} is outside current groupings.")
        return grouped

class EventFetcher:
    def __init__(self):
        self.substrates = {}  # group_id -> AsyncSubstrateInterface

    async def initialize_substrate_connections(self):
        bt.logging.info("Initializing Event Fetcher")
        for group, init_block in GROUP_INIT_BLOCK.items():
            bt.logging.info(f"Initializing substrate for group {group} @ block {init_block}")
            substrate = AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS)
            init_hash = await substrate.get_block_hash(init_block)
            await substrate.init_runtime(block_hash=init_hash)
            self.substrates[group] = substrate

    async def get_current_block(self) -> int:

        current_block = await self.substrates[6].get_block()

        return current_block['header']['number']

    async def get_block_events(
        self, 
        substrate: AsyncSubstrateInterface, 
        block_info: List[Tuple[int, str]], 
        max_concurrent: int = 10
    ) -> Dict[int, Any]:
        """
        Fetch events for a list of blocks.
        
        Parameters:
            substrate: The substrate interface for RPC calls.
            block_info: List of tuples (block_number, block_hash).
            max_concurrent: Maximum number of concurrent RPC calls.
            
        Returns:
            A dictionary mapping block number to event response.
        """
        # Extract block hashes for processing.
        block_hashes = [block_hash for (_, block_hash) in block_info]
        semaphore = asyncio.Semaphore(max_concurrent)

        async def preprocess_with_semaphore(block_hash):
            async with semaphore:
                return await substrate._preprocess(
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
            substrate.make_payload(
                f"{block_hash}",
                preprocessed.method,
                [preprocessed.params[0], block_hash]
            )
            for block_hash, preprocessed in zip(block_hashes, preprocessed_lst)
        ]

        responses = await asyncio.wait_for(
            substrate._make_rpc_request(
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
    

    async def fetch_all_events(self, block_numbers: List[int]) -> Dict[int, Any]:
        """
        Retrieve events for all given block numbers.
        
        Parameters:
            block_numbers: A list of block numbers.
            
        Returns:
            A dictionary mapping block numbers to their event responses.
        """
        start_time = time.time()
        bt.logging.debug(f"\nAttempting to fetching event data, for {len(block_numbers)} blocks...")

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

        # Get block hashes from substrate 1 (assuming all substrates return consistent hashes).
        block_hashes = await asyncio.gather(
            *[self.substrates[1].get_block_hash(n) for n in block_numbers]
        )

        # Need to make sure we always use the latest substrate to get the current block otherwise it can throw off older substrate
        current_block = await self.get_current_block()

        # Group blocks by group while maintaining the block number alongside its hash.
        grouped = group_blocks(block_numbers, block_hashes, current_block)

        all_events: Dict[int, Any] = {}
        for group, block_info in grouped.items():
            bt.logging.debug(f"\nFetching events for group {group} ({len(block_info)} blocks)...")
            substrate = self.substrates[group]
            attempts = 3
            for attempt in range(attempts):
                try:
                    events = await self.get_block_events(substrate, block_info)
                    all_events.update(events)
                    bt.logging.debug(f"Successfully fetched events for group {group} on attempt {attempt+1}.")
                    break  # Exit retry loop on success.
                except Exception as e:
                    if attempt < attempts - 1:
                        bt.logging.error(
                            f"Error fetching events for group {group} on attempt {attempt+1}: {e}. Retrying..."
                        )
                    else:
                        bt.logging.error(
                            f"Error fetching events for group {group} on final attempt: {e}. Continuing..."
                        )
            # Continue to next group even if the current one fails.
        bt.logging.debug(f"All events collected in {time.time() - start_time} seconds.")
        return all_events

async def example():

    bt.debug()

    fetcher = EventFetcher()
    await fetcher.initialize_substrate_connections()

    test_cases = [
        [5163655 + i for i in range(500)]
        # [3804341, 3804339, 3804340, 3804341, 4264339, 4264340, 4264341, 4920349, 4920350, 4920351, 5163655, 5163656, 5163657, 5228683, 5228684, 5228685]
        # [3804341, 3804341],   # duplicates
        # [3014322],  # block number is too early
        # [6000000],  # block number is too later
        # [],   # empty input
        # ["str_input", 3804339],   # invalid types in input
        # [3804341 + i for i in range(1000)]    # high volume
    ]

    failing_test_cases = [[4264340 + i] for i in range(500)]
    #     # [4264440 + i for i in range(100)],
    #     # [4264540 + i for i in range(100)],
    #     # [4264640 + i for i in range(100)],
    #     # [4264740 + i for i in range(100)]
    #     [4264632]
    # ]

    for test_case in test_cases:

        bt.logging.info("Starting next test case.")

        start_time = time.time()
        all_events = await fetcher.fetch_all_events(test_case)
        bt.logging.info(f"\n✅ Retrieved events for {len(all_events)} blocks in {time.time() - start_time:.2f} seconds.")

        filename = 'new_event_data.json'
        import json

        # Open the file in write mode and dump the dictionary to it
        with open(filename, 'w') as json_file:
            json.dump(all_events, json_file, indent=4)
        # bt.logging.debug(all_events)

if __name__ == "__main__":
    asyncio.run(example())