import time
import asyncio
import random
import logging

from bittensor import AsyncSubtensor

from patrol.constants import Constants
from patrol.chain_data.event_fetcher import EventFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_random_block_tuples(subtensor: AsyncSubtensor, num_targets: int = 1) -> tuple(int, str):

    current_block = await subtensor.get_current_block()
    start_block = random.randint(3_014_340, current_block)
    block_numbers = [start_block + i for i in range(num_targets)]

    tasks = [subtensor.substrate.get_block_hash(block_id=block_number) for block_number in block_numbers]

    block_hashes = await asyncio.gather(*tasks)
    return zip(block_numbers, block_hashes)

async def assign_targets(events, number_targets: int):

    # The functionality in here will fill out once we know the format back from the get events. 

    for block_hash, value in events.items():
        print(f"Block {block_hash}: {value}")

    return [(1, 100), (2, 101)]

async def generate_targets(subtensor: AsyncSubtensor, event_fetcher: EventFetcher, num_targets: int = 1):

    logger.info(f"Fetching {num_targets} target addresses.")

    block_tuples = await generate_random_block_tuples(subtensor, num_targets)

    events = event_fetcher.get_block_events(block_tuples)

    target_tuples = await assign_targets(events, num_targets)

    return target_tuples

if __name__ == "__main__":
    asyncio.run(generate_targets(10))