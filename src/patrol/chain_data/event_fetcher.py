import asyncio
import time
from typing import Dict, List, Tuple, Any
import bittensor as bt

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
    current_block: int,
    batch_size: int = 500
) -> Dict[int, List[List[Tuple[int, str]]]]:
    """
    Groups blocks by group ID and splits each group into batches.

    Args:
        block_numbers: List of block numbers.
        block_hashes: Corresponding block hashes.
        current_block: Current latest block.
        batch_size: Maximum number of blocks per batch (default 500).

    Returns:
        Dictionary mapping group ID to list of block batches (each a list of tuples).
    """
    grouped: Dict[int, List[Tuple[int, str]]] = {}
    for block_number, block_hash in zip(block_numbers, block_hashes):
        group = group_block(block_number, current_block)
        if group:
            grouped.setdefault(group, []).append((block_number, block_hash))
        else:
            bt.logging.warning(f"Block {block_number} is outside current groupings.")

    batched: Dict[int, List[List[Tuple[int, str]]]] = {}
    for group_id, block_list in grouped.items():
        batched[group_id] = [
            block_list[i:i + batch_size] for i in range(0, len(block_list), batch_size)
        ]

    return batched

class EventFetcher:
    def __init__(self, substrate_client):
        self.substrate_client = substrate_client
        self.semaphore = asyncio.Semaphore(1)
  
    async def get_current_block(self) -> int:
        current_block = await self.substrate_client.query(6, "get_block")
        return current_block["header"]["number"]

    async def get_block_events(
        self,
        group: int,
        block_info: List[Tuple[int, str]],
        max_concurrent: int = 10
    ) -> Dict[int, Any]:
        """
        Fetch events for a batch of blocks for a specific group using the substrate client's query method.
        """
        # Extract block hashes for processing.
        block_hashes = [block_hash for (_, block_hash) in block_info]
        semaphore = asyncio.Semaphore(max_concurrent)

        async def preprocess_with_semaphore(block_hash):
            async with semaphore:
                # Use the query method to call the substrate's _preprocess method.
                return await self.substrate_client.query(
                    group,
                    "_preprocess",
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

        payloads = self.substrate_client.build_payloads(group, block_hashes, preprocessed_lst)

        responses = await asyncio.wait_for(
            self.substrate_client.query(
                group,
                "_make_rpc_request",
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
                self.substrate_client.query(6, "get_block_hash", n)
                for n in block_numbers
            ]
            block_hashes = await asyncio.gather(*block_hash_tasks)

            # Need to make sure we always use the latest substrate to get the current block otherwise it can throw off older substrate
            current_block = await self.get_current_block()

            # Group blocks by group while maintaining the block number alongside its hash.
            grouped = group_blocks(block_numbers, block_hashes, current_block)

            all_events: Dict[int, Any] = {}
            for group, batches in grouped.items():
                for batch in batches:
                    bt.logging.debug(f"\nFetching events for group {group} (batch of {len(batch)} blocks)...")
                    try:
                        events = await self.get_block_events(group, batch)
                        all_events.update(events)
                        bt.logging.debug(f"Successfully fetched events for group {group} batch.")
                    except Exception as e:
                        bt.logging.warning(
                            f"Error fetching events for group {group} batch on final attempt: {e}. Continuing..."
                        )
            # Continue to next group even if the current one fails.
        bt.logging.debug(f"All events collected in {time.time() - start_time} seconds.")
        return all_events

async def example():

    bt.debug()

    from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK

    network_url = "wss://archive.chain.opentensor.ai:443/"
        
    # Create an instance of SubstrateClient.
    client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=30, max_retries=3)
    
    # Initialize substrate connections for all groups.
    await client.initialize_connections()

    fetcher = EventFetcher(substrate_client=client)

    test_cases = [
        [5163655 + i for i in range(1000)]
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
        bt.logging.info(f"\nRetrieved events for {len(all_events)} blocks in {time.time() - start_time:.2f} seconds.")

        filename = 'new_event_data.json'
        import json

        # Open the file in write mode and dump the dictionary to it
        with open(filename, 'w') as json_file:
            json.dump(all_events, json_file, indent=4)
        # bt.logging.debug(all_events)

if __name__ == "__main__":
    asyncio.run(example())