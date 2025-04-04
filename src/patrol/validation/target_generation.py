import random
import time
from typing import List, Tuple

import bittensor as bt

from patrol.chain_data.get_current_block import get_current_block
from patrol.chain_data.event_parser import process_event_data
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder

class TargetGenerator:
    def __init__(self, event_fetcher: EventFetcher, coldkey_finder: ColdkeyFinder):
        self.event_fetcher = event_fetcher
        self.coldkey_finder = coldkey_finder

    async def generate_random_block_tuples(self, num_targets: int = 1) -> List[int]:
        current_block = await get_current_block(self.coldkey_finder.substrate)   # borrowing the substrate connection
        start_block = random.randint(3_014_342, current_block - num_targets * 4 * 600)
        return [start_block + i * 500 for i in range(num_targets * 4)]

    async def find_targets(self, events, number_targets: int) -> List[Tuple[str, int]]:
        target_set = set()
        for event in events:
            block = event.get("evidence", {}).get("block_number")
            for key in ("coldkey_source", "coldkey_destination", "coldkey_owner"):
                addr = event.get(key)
                if addr and block:
                    target_set.add((addr, block))
        return random.sample(list(target_set), min(number_targets, len(target_set)))

    async def generate_targets(self, num_targets: int = 1) -> List[Tuple[str, int]]:
        bt.logging.info(f"Fetching {num_targets} target addresses.")
        start_time = time.time()

        block_numbers = await self.generate_random_block_tuples(num_targets)
        events = await self.event_fetcher.fetch_all_events(block_numbers)
        processed_events = await process_event_data(events, self.coldkey_finder)
        target_tuples = await self.find_targets(processed_events, num_targets)

        while len(target_tuples) < num_targets:
            if not target_tuples:
                break
            target_tuples.append(random.choice(target_tuples))

        bt.logging.info(f"Returning {len(target_tuples)} targets, in {time.time() - start_time} seconds.")
        return target_tuples

if __name__ == "__main__":

    import asyncio

    async def example():

        bt.debug()

        fetcher = EventFetcher()
        await fetcher.initialise_substrate_connections()

        coldkey_finder = ColdkeyFinder()
        await coldkey_finder.initialise_substrate_connection()

        target_generator = TargetGenerator(fetcher, coldkey_finder)

        target_tuples = await target_generator.generate_targets(247)

        bt.logging.info(f"Returned: {len(target_tuples)} targets.")

    asyncio.run(example())