import random
import time
from typing import List, Tuple

import bittensor as bt

from patrol.chain_data.event_processor import EventProcessor
from patrol.chain_data.event_fetcher import EventFetcher

class TargetGenerator:
    def __init__(self, event_fetcher: EventFetcher, event_processor: EventProcessor):
        self.event_fetcher = event_fetcher
        self.event_processor = event_processor

    async def generate_random_block_tuples(self, num_targets: int = 1) -> List[int]:
        current_block = await self.event_fetcher.get_current_block()
        start_block = random.randint(3_014_342, current_block - num_targets * 4 * 600)
        return [start_block + i * 500 for i in range(num_targets * 4)]

    async def find_targets(self, events, number_targets: int) -> List[Tuple[str, int]]:
        target_set = set()
        for event in events:
            if not isinstance(event, dict):
                continue
            block = event.get("evidence", {}).get("block_number")
            for key in ("coldkey_source", "coldkey_destination", "coldkey_owner"):
                addr = event.get(key)
                if addr and block:
                    target_set.add((addr, block))
        return random.sample(list(target_set), min(number_targets, len(target_set)))

    async def generate_targets(self, num_targets: int = 1) -> List[Tuple[str, int]]:
        bt.logging.debug(f"Fetching {num_targets} target addresses.")
        start_time = time.time()

        block_numbers = await self.generate_random_block_tuples(num_targets)
        events = await self.event_fetcher.fetch_all_events(block_numbers)
        processed_events = await self.event_processor.process_event_data(events)
        target_tuples = await self.find_targets(processed_events, num_targets)

        while len(target_tuples) < num_targets:
            if not target_tuples:
                break
            target_tuples.append(random.choice(target_tuples))

        bt.logging.info(f"Returning {len(target_tuples)} targets, in {time.time() - start_time} seconds.")
        return target_tuples[:num_targets]

if __name__ == "__main__":

    import asyncio

    from patrol.chain_data.coldkey_finder import ColdkeyFinder
    from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK

    async def example():

        bt.debug()

        network_url = "wss://archive.chain.opentensor.ai:443/"
            
        # Create an instance of SubstrateClient.
        client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=30, max_retries=3)
        
        # Initialize substrate connections for all groups.
        await client.initialize_connections()

        fetcher = EventFetcher(substrate_client=client)
        coldkey_finder = ColdkeyFinder(substrate_client=client)
        event_processor = EventProcessor(coldkey_finder=coldkey_finder)

        target_generator = TargetGenerator(fetcher, event_processor)

        target_tuples = await target_generator.generate_targets(247)

        bt.logging.info(f"Returned: {len(target_tuples)} targets.")

    asyncio.run(example())