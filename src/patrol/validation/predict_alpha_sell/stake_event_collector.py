import asyncio
import logging

from sqlalchemy.ext.asyncio import create_async_engine
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.chain.runtime_versions import RuntimeVersions
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository
from patrol.validation.predict_alpha_sell import AlphaSellEventRepository, AlphaSellChallengeRepository

batch_size = 1000
max_back_off = 12
max_block_retardation = 10
prune_interval = 60

logger = logging.getLogger(__name__)

class StakeEventCollector:
    def __init__(self, chain_reader: ChainReader,
                 alpha_sell_event_repository: AlphaSellEventRepository,
                 alpha_sell_challenge_repository: AlphaSellChallengeRepository
    ):
        self.chain_reader = chain_reader
        self.alpha_sell_event_repository = alpha_sell_event_repository
        self.alpha_sell_challenge_repository = alpha_sell_challenge_repository

    async def collect_events(self) -> int:
        previous_block = await self.chain_reader.get_current_block() - 1
        most_recent_block = await self.alpha_sell_event_repository.find_most_recent_block_collected()

        starting_block = most_recent_block + 1 if most_recent_block else previous_block - 10

        retardation = previous_block - starting_block
        if retardation < max_block_retardation:
            logger.info("Skipping event collection because the events are within [%s] blocks of the current block", retardation)
            return max_back_off

        logger.info("Collecting stake events from block %s - %s", starting_block, previous_block)

        blocks_to_collect = range(starting_block, previous_block)

        def block_batches():
            for i in range(0, len(blocks_to_collect), batch_size):
                yield blocks_to_collect[i:i + batch_size]

        for batch in block_batches():
            events = await self.chain_reader.find_stake_events(batch)
            await self.alpha_sell_event_repository.add(events)

        return 0

    async def prune_events(self):
        earliest_block = await self.alpha_sell_challenge_repository.find_earliest_prediction_block()
        if earliest_block:
            events_deleted = await self.alpha_sell_event_repository.delete_events_before_block(earliest_block)
            logger.info("Deleted [%s] events before block [%s]", events_deleted, earliest_block)
        else:
            events_deleted = await self.alpha_sell_event_repository.delete_events_before_block(10_000_000)
            logger.info("Deleted [%s] events before block [%s]", events_deleted, earliest_block)

    async def collect_events_forever(self):
        logger.info("Starting StakeEventCollector")
        while True:
            try:
                back_off = await asyncio.create_task(self.collect_events())
                await asyncio.sleep(back_off)
                if back_off > 0:
                    await asyncio.create_task(self.prune_events())

            except Exception as e:
                logger.exception("Unexpected error")


def start(db_url: str):
    from patrol.validation.config import ARCHIVE_SUBTENSOR

    async def async_start():
        runtime_versions = RuntimeVersions()
        active_versions = {k: v for k, v in runtime_versions.versions.items() if int(k) >= 261}

        substrate_client = SubstrateClient(active_versions, ARCHIVE_SUBTENSOR)
        await substrate_client.initialize()

        engine = create_async_engine(db_url)
        event_repository = DataBaseAlphaSellEventRepository(engine)
        chain_reader = ChainReader(substrate_client, runtime_versions)

        alpha_sell_challenge_repository = DatabaseAlphaSellChallengeRepository(engine)

        collector = StakeEventCollector(chain_reader, event_repository, alpha_sell_challenge_repository)
        await collector.collect_events_forever()

    asyncio.run(async_start())


def start_process(db_url: str):
    import multiprocessing
    p = multiprocessing.Process(target=start, name="Event Collector", args=[db_url], daemon=True)
    p.start()
    return p

if __name__ == "__main__":
    start_process("postgresql+asyncpg://patrol:password@localhost:5432/patrol")