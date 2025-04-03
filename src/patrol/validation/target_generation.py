import asyncio
import random
from typing import List, Tuple

import bittensor as bt
from async_substrate_interface import AsyncSubstrateInterface

from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.constants import Constants
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.get_current_block import get_current_block
from patrol.chain_data.event_parser import process_event_data

async def generate_random_block_tuples(substrate:AsyncSubstrateInterface, num_targets: int = 1) -> List[int]:

    current_block = await get_current_block(substrate)
    start_block = random.randint(3_014_342, current_block - num_targets*4*600)   # giving ourselves a buffer and a good selection of blocks
    return [start_block + i*500 for i in range(num_targets*4)]

async def find_targets(events, number_targets: int) -> List[Tuple[str, int]]:
    target_set = set()

    for event in events:
        block = event.get("evidence", {}).get("block_number")
        for key in ("coldkey_source", "coldkey_destination", "coldkey_owner"):
            addr = event.get(key)
            if addr and block:
                target_set.add((addr, block))

    return random.sample(list(target_set), min(number_targets, len(target_set)))

async def generate_targets(substrate: AsyncSubstrateInterface, event_fetcher: EventFetcher, coldkey_finder: ColdkeyFinder, num_targets: int = 1):
    bt.logging.info(f"Fetching {num_targets} target addresses.")

    block_numbers = await generate_random_block_tuples(substrate, num_targets)
    events = await event_fetcher.fetch_all_events(block_numbers)
    processed_events = await process_event_data(events, coldkey_finder)
    target_tuples = await find_targets(processed_events, num_targets)

    while len(target_tuples) < num_targets:
        if not target_tuples:
            break  # prevent infinite loop
        target_tuples.append(random.choice(target_tuples))

    return target_tuples

if __name__ == "__main__":

    from patrol.constants import Constants

    async def example():

        bt.debug()

        fetcher = EventFetcher()
        await fetcher.initialise_substrate_connections()

        async with AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS) as substrate:

            coldkey_finder = ColdkeyFinder(substrate)

            target_tuples = await generate_targets(substrate, fetcher, coldkey_finder, 247)

            bt.logging.info(f"Returned: {len(target_tuples)} targets.")

    asyncio.run(example())