import asyncio
import logging
import multiprocessing
import random
import uuid

from bittensor import AsyncSubtensor, Dendrite
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation import Miner
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, \
    HotkeyOwnershipValidator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence.miner_score_repository import DatabaseMinerScoreRepository

logger = logging.getLogger(__name__)

class HotkeyOwnershipBatch:

    def __init__(self,
                 challenge: HotkeyOwnershipChallenge,
                 target_generator: HotkeyTargetGenerator,
                 metagraph: AsyncMetagraph,
                 chain_reader: ChainReader,
                 concurrency: int
     ):
        self.challenge = challenge
        self.target_generator = target_generator
        self.metagraph = metagraph
        self.chain_reader = chain_reader
        self.concurrency_semaphore = asyncio.Semaphore(concurrency)

    async def challenge_miners(self):

        await self.metagraph.sync()

        current_block = await self.chain_reader.get_current_block()
        max_block_number = current_block - 10

        batch_id = uuid.uuid4()
        logging_extra = {"batch_id": str(batch_id)}

        logger.info("Batch started", extra=logging_extra)

        axons = self.metagraph.axons
        uids = self.metagraph.uids.tolist()

        miners = list(filter(
            lambda m: m.axon_info.is_serving,
            (Miner(axon, uids[idx]) for idx, axon in enumerate(axons))
        ))
        logger.info("Challenging %s miners", len(miners))

        target_hotkeys = await self.target_generator.generate_targets(max_block_number, len(miners))
        miner_target_hotkeys = {miner.uid: target_hotkeys.pop() for miner in miners}

        random.shuffle(miners)

        async def challenge(miner):
            try:
                async with self.concurrency_semaphore:
                    await self.challenge.execute_challenge(miner, miner_target_hotkeys[miner.uid], batch_id, max_block_number)
            except Exception as ex:
                logger.exception("Unhandled error: %s", ex)

        challenge_tasks = [challenge(miner) for miner in miners]
        await asyncio.gather(*challenge_tasks)

        logger.info("Batch completed", extra=logging_extra)

        return batch_id

async def run_forever(wallet: Wallet, db_url: str, patrol_subtensor: AsyncSubtensor, patrol_metagraph: AsyncMetagraph, enable_dashboard_syndication: bool):
    from patrol.validation.config import DASHBOARD_BASE_URL, NET_UID, BATCH_CONCURRENCY, ARCHIVE_SUBTENSOR

    engine = create_async_engine(db_url)
    archive_subtensor = AsyncSubtensor(ARCHIVE_SUBTENSOR)
    chain_reader = ChainReader(archive_subtensor.substrate)

    dendrite = Dendrite(wallet)
    miner_client = HotkeyOwnershipMinerClient(dendrite)
    scoring = HotkeyOwnershipScoring()
    validator = HotkeyOwnershipValidator(chain_reader)
    score_repository = DatabaseMinerScoreRepository(engine)
    dashboard_client = HttpDashboardClient(wallet, DASHBOARD_BASE_URL) if enable_dashboard_syndication else None

    challenge = HotkeyOwnershipChallenge(
        miner_client=miner_client,
        scoring=scoring,
        validator=validator,
        score_repository=score_repository,
        dashboard_client=dashboard_client
    )

    target_generator = HotkeyTargetGenerator(archive_subtensor.substrate)
    patrol_metagraph = await patrol_subtensor.metagraph(NET_UID) if patrol_metagraph is None else patrol_metagraph

    batch = HotkeyOwnershipBatch(
        challenge=challenge,
        target_generator=target_generator,
        metagraph=patrol_metagraph,
        chain_reader=chain_reader,
        concurrency=BATCH_CONCURRENCY
    )

    while True:
        try:
            await batch.challenge_miners()
        finally:
            await asyncio.sleep(600)


async def run(wallet: Wallet, db_url: str, subtensor: AsyncSubtensor, enable_dashboard_syndication: bool,
              patrol_metagraph: AsyncMetagraph | None):
    if subtensor:
        await run_forever(wallet, db_url, subtensor, patrol_metagraph, enable_dashboard_syndication)
    else:
        from patrol.validation.config import ARCHIVE_SUBTENSOR
        async with AsyncSubtensor(ARCHIVE_SUBTENSOR) as st:
            await run_forever(wallet, db_url, st, patrol_metagraph, enable_dashboard_syndication)


def start_process(
        wallet: Wallet,
        db_url: str,
        enable_dashboard_syndication: bool,
        subtensor: AsyncSubtensor | None = None,
        patrol_metagraph: AsyncMetagraph | None = None,
) -> multiprocessing.Process:

    def run_async():
        asyncio.run(run(wallet, db_url, subtensor, enable_dashboard_syndication, patrol_metagraph))

    process = multiprocessing.Process(target=run_async(), name="Hotkey Ownership Challenge", daemon=True)
    process.start()
    return process

