import asyncio
import logging

from async_substrate_interface import AsyncSubstrateInterface
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation import hooks
from patrol.validation.aws_rds import consume_db_engine
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hooks import HookType
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository
from patrol.validation.predict_alpha_sell import AlphaSellEventRepository, AlphaSellChallengeRepository

batch_size = 100
back_off = 12

logger = logging.getLogger(__name__)

class StakeEventCollector:
    def __init__(self, chain_reader: ChainReader,
                 alpha_sell_event_repository: AlphaSellEventRepository,
                 alpha_sell_challenge_repository: AlphaSellChallengeRepository
    ):
        self.chain_reader = chain_reader
        self.alpha_sell_event_repository = alpha_sell_event_repository
        self.alpha_sell_challenge_repository = alpha_sell_challenge_repository

    async def collect_events(self):
        last_finalized_block = await self.chain_reader.get_last_finalized_block()
        most_recent_block_collected = await self.alpha_sell_event_repository.find_most_recent_block_collected()

        earliest_block_required = await self.alpha_sell_challenge_repository.find_earliest_prediction_block()
        if (earliest_block_required is None) or (earliest_block_required > last_finalized_block):
            logger.info("Earliest block required [%s] is after current block [%s]- skipping", earliest_block_required, last_finalized_block)
            return

        most_recent_block_collected = last_finalized_block - 5 if most_recent_block_collected is None else most_recent_block_collected

        block_deficit = max(0, last_finalized_block - most_recent_block_collected)

        logger.info("Most recent block collected = %s; latest finalized block = %s; deficit = %s",
                    most_recent_block_collected, last_finalized_block, block_deficit
        )

        if block_deficit == 0:
            logger.info("Skipping event collection because the events are within [%s] blocks of the last finalized block", block_deficit)
            return

        starting_block = most_recent_block_collected + 1
        logger.info("Collecting stake events from block %s - %s inclusive", starting_block, last_finalized_block)

        blocks_to_collect = range(starting_block, last_finalized_block + 1)

        def block_batches():
            for i in range(0, len(blocks_to_collect), batch_size):
                yield blocks_to_collect[i:i + batch_size]

        for batch in block_batches():
            events = await self.chain_reader.find_stake_events(batch)
            await self.alpha_sell_event_repository.add(events)
            logger.info("Collected %s events from %s block(s)", len(events), len(batch))


    async def prune_events(self):
        earliest_block = await self.alpha_sell_challenge_repository.find_earliest_prediction_block()
        if earliest_block:
            events_deleted = await self.alpha_sell_event_repository.delete_events_before_block(earliest_block)
            logger.info("Deleted [%s] events before block [%s]", events_deleted, earliest_block)

    async def collect_events_forever(self):
        logger.info("Starting StakeEventCollector")
        while True:
            try:
                await asyncio.create_task(self.collect_events())
                await asyncio.sleep(back_off)
                await asyncio.create_task(self.prune_events())
            except Exception as e:
                logger.exception("Unexpected error")


async def start(db_url: str):
    from patrol.validation.config import ARCHIVE_SUBTENSOR, ENABLE_AWS_RDS_IAM

    if ENABLE_AWS_RDS_IAM:
        hooks.add_on_create_db_engine(consume_db_engine)

    async with AsyncSubstrateInterface(ARCHIVE_SUBTENSOR) as substrate:
        engine = create_async_engine(db_url)
        hooks.invoke(HookType.ON_CREATE_DB_ENGINE, engine)
        event_repository = DataBaseAlphaSellEventRepository(engine)
        chain_reader = ChainReader(substrate)

        alpha_sell_challenge_repository = DatabaseAlphaSellChallengeRepository(engine)

        collector = StakeEventCollector(chain_reader, event_repository, alpha_sell_challenge_repository)
        await collector.collect_events_forever()


def start_process(db_url: str):

    def start_async():
        asyncio.run(start(db_url))

    import multiprocessing
    p = multiprocessing.Process(target=start_async, name="Event Collector", daemon=True)
    p.start()
    return p
