import asyncio
import logging
import multiprocessing
import random
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, UTC

import bittensor as bt
from bittensor import AsyncSubtensor
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation import TaskType, hooks
from patrol.validation.aws_rds import consume_db_engine
from patrol.validation.dashboard import DashboardClient
from patrol.validation.error import MinerTaskException
from patrol.validation.hooks import HookType
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellChallengeMiner, PredictionInterval, WalletIdentifier
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.scoring import MinerScore
from patrol_common.protocol import AlphaSellSynapse

logger = logging.getLogger(__name__)


class AlphaSellMinerChallenge:

    def __init__(self,
                 miner_client: AlphaSellMinerClient,
                 dashboard_client: DashboardClient | None
    ):
        self.miner_client = miner_client
        self.dashboard_client = dashboard_client

    async def execute_challenge(self, miner: Miner, batches: list[AlphaSellChallengeBatch]) -> AsyncGenerator[AlphaSellChallengeTask]:
        synapses = [AlphaSellSynapse(
            batch_id=str(batch.batch_id),
            task_id=str(uuid.uuid4()),
            subnet_uid=batch.subnet_uid,
            prediction_interval=batch.prediction_interval,
            wallets=batch.wallets,
        ) for batch in batches]

        responses = await self.miner_client.execute_tasks(miner.axon_info, synapses)
        miner = AlphaSellChallengeMiner(miner.axon_info.hotkey, miner.axon_info.coldkey, miner.uid)
        for response in responses:
            if isinstance(response, MinerTaskException):
                logger.warning("Exception during challenge execution: %s", response)
                now = datetime.now(UTC)
                task = AlphaSellChallengeTask(
                    has_error=True,
                    error_message=str(response),
                    batch_id=response.batch_id,
                    created_at=now,
                    task_id=response.task_id,
                    predictions=[],
                    miner=miner,
                )
                try:
                    if self.dashboard_client:
                        await self.send_zero_score_to_dashboard(task)
                except Exception:
                    logger.exception("Error sending zero score to dashboard")

            else:
                batch_id, task_id, synapse = response
                now = datetime.now(UTC)
                task = AlphaSellChallengeTask(
                    batch_id=batch_id,
                    created_at=now,
                    task_id=task_id,
                    predictions=synapse.predictions,
                    miner=miner,
                )

            yield task

    async def send_zero_score_to_dashboard(self, task: AlphaSellChallengeTask):
        await self.dashboard_client.send_scores([MinerScore(
            id=task.task_id,
            batch_id=task.batch_id,
            created_at=datetime.now(UTC),
            uid=task.miner.uid,
            coldkey=task.miner.coldkey,
            hotkey=task.miner.hotkey,
            overall_score_moving_average=0,
            overall_score=0,
            volume_score=0,
            volume=0,
            responsiveness_score=0,
            response_time_seconds=0,
            novelty_score=0,
            validation_passed=not task.has_error,
            error_message=task.error_message,
            accuracy_score=0,
            task_type=TaskType.PREDICT_ALPHA_SELL
        )])

class AlphaSellMinerChallengeProcess:

    def __init__(self,
                 challenge_repository: AlphaSellChallengeRepository,
                 miner_challenge: AlphaSellMinerChallenge,
                 subtensor: AsyncSubtensor,
                 patrol_metagraph: AsyncMetagraph,
                 interval_window_blocks: int,
                 start_block_offset: int
    ):
        self.challenge_repository = challenge_repository
        self.miner_challenge = miner_challenge
        self.subtensor = subtensor
        self.patrol_metagraph = patrol_metagraph
        self.interval_window_blocks = interval_window_blocks
        self.start_block_offset = start_block_offset

    @classmethod
    async def create(cls,
                     challenge_repository: AlphaSellChallengeRepository,
                     miner_challenge: AlphaSellMinerChallenge,
                     subtensor: AsyncSubtensor,
                     patrol_metagraph: AsyncMetagraph | None,
                     interval_window_blocks: int = 7200,
                     start_block_offset: int = 5,
    ):
        patrol_metagraph = await subtensor.metagraph(81) if patrol_metagraph is None else patrol_metagraph
        return cls(challenge_repository, miner_challenge, subtensor, patrol_metagraph,
                   interval_window_blocks=interval_window_blocks,
                   start_block_offset=start_block_offset
        )

    async def challenge_miners(self):

        logger.info("Preparing Miner Challenges for prediction window: %s blocks", self.interval_window_blocks)

        current_block = await self.subtensor.get_current_block()
        start_block = current_block + 5
        prediction_interval = PredictionInterval(start_block, start_block + self.interval_window_blocks)

        await self.patrol_metagraph.sync()
        logger.info("Metagraph synced")

        axons = self.patrol_metagraph.axons
        uids = self.patrol_metagraph.uids.tolist()

        miners_to_challenge = list(filter(
            lambda m: m.axon_info.is_serving,
            (Miner(axon, uids[idx]) for idx, axon in enumerate(axons))
        ))

        subnets = [sn for sn in await self.subtensor.get_subnets() if sn not in {0, 81}]
        scoring_sequence = await self.challenge_repository.get_next_scoring_sequence()
        batches = [await self._make_batch(prediction_interval, net_uid, scoring_sequence) for net_uid in subnets]

        logger.info("Challenge batch preparation for %s subnets", len(batches))
        for batch in batches:
            await self.challenge_repository.add(batch)

        logger.info("Executing Miner Challenges for prediction window: %s blocks", self.interval_window_blocks)
        
        shuffled_miners = random.sample(miners_to_challenge, len(miners_to_challenge))
        
        for miner in shuffled_miners:
            shuffled_batches = random.sample(batches, len(batches))

            async for task in self.miner_challenge.execute_challenge(miner, shuffled_batches):
                # TODO tolerate a failure to persist?
                await self.challenge_repository.add_task(task)
                logger.info("Received task response from miner", extra={'miner': miner.axon_info})

                #if not task.has_error:
                #    tasks_to_syndicate.append(task)
            # TODO: Send to API if OK

        await self.challenge_repository.mark_batches_ready_for_scoring([b.batch_id for b in batches])

        logger.info("Miner Challenges complete.")

    async def _make_batch(self, prediction_interval: PredictionInterval, net_uid: int, scoring_sequence: int):
        metagraph = await self.subtensor.metagraph(net_uid)
        logger.info("Metagraph for subnet %s loaded", net_uid)
        wallets = [WalletIdentifier(i.coldkey, i.hotkey) for i in metagraph.axons]

        batch_id = uuid.uuid4()
        return AlphaSellChallengeBatch(batch_id, datetime.now(UTC), net_uid, prediction_interval, wallets, scoring_sequence)


async def run_forever(wallet: Wallet, subtensor: AsyncSubtensor, db_url: str, enable_dashboard_syndication: bool,
                      patrol_metagraph: AsyncMetagraph | None):

    from patrol.validation.config import ENABLE_AWS_RDS_IAM
    if ENABLE_AWS_RDS_IAM:
        hooks.add_on_create_db_engine(consume_db_engine)

    engine = create_async_engine(db_url)
    hooks.invoke(HookType.ON_CREATE_DB_ENGINE, engine)

    challenge_repository = DatabaseAlphaSellChallengeRepository(engine)
    dendrite = bt.Dendrite(wallet)
    miner_client = AlphaSellMinerClient(dendrite)

    from patrol.validation.config import DASHBOARD_BASE_URL, ALPHA_SELL_PREDICTION_WINDOW_BLOCKS, \
        ALPHA_SELL_TASK_INTERVAL_SECONDS

    dashboard_client = HttpDashboardClient(wallet, DASHBOARD_BASE_URL) if enable_dashboard_syndication else None

    miner_challenge = AlphaSellMinerChallenge(miner_client, dashboard_client)

    process = await AlphaSellMinerChallengeProcess.create(
        challenge_repository, miner_challenge, subtensor, patrol_metagraph,
        interval_window_blocks=ALPHA_SELL_PREDICTION_WINDOW_BLOCKS
    )

    while True:
        try:
            await process.challenge_miners()
        except Exception as ex:
            logger.exception("Unexpected error")
        finally:
            await asyncio.sleep(ALPHA_SELL_TASK_INTERVAL_SECONDS)

async def run(wallet: Wallet, subtensor: AsyncSubtensor, db_url: str, enable_dashboard_syndication: bool,
              patrol_metagraph: AsyncMetagraph):
    if subtensor:
        await run_forever(wallet, subtensor, db_url, enable_dashboard_syndication, patrol_metagraph)
    else:
        from patrol.validation.config import ARCHIVE_SUBTENSOR
        async with AsyncSubtensor(ARCHIVE_SUBTENSOR) as st:
            await run_forever(wallet, st, db_url, enable_dashboard_syndication, patrol_metagraph)


def start_process(
        wallet: Wallet,
        db_url: str,
        enable_dashboard_syndication: bool,
        subtensor: AsyncSubtensor | None = None,
        patrol_metagraph: AsyncMetagraph | None = None
):
    def run_async():
        asyncio.run(run(wallet, subtensor, db_url, enable_dashboard_syndication, patrol_metagraph))

    process = multiprocessing.Process(target=run_async, name="Challenge", daemon=True)
    process.start()
    return process
