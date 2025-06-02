import asyncio
import logging
import multiprocessing
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, UTC
from tempfile import TemporaryDirectory

import bittensor as bt
from bittensor import AsyncSubtensor
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.constants import TaskType
from patrol.validation.dashboard import DashboardClient
from patrol.validation.error import MinerTaskException
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellChallengeMiner, PredictionInterval
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse
from patrol.validation.scoring import MinerScore

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
            wallet_hotkeys_ss58=batch.hotkeys_ss58,
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
        await self.dashboard_client.send_score(MinerScore(
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
        ))

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

        logger.info("Executing Miner Challenges for prediction window: %s blocks", self.interval_window_blocks)

        current_block = await self.subtensor.get_current_block()
        start_block = current_block + 5
        prediction_interval = PredictionInterval(start_block, start_block + self.interval_window_blocks)

        await self.patrol_metagraph.sync()
        miners_to_challenge = [Miner(axon, idx) for idx, axon in enumerate(self.patrol_metagraph.axons) if axon.is_serving]

        subnets = await self.subtensor.get_subnets()
        batches = [await self._make_batch(prediction_interval, net_uid) for net_uid in subnets]

        for batch in batches:
            await self.challenge_repository.add(batch)

        for miner in miners_to_challenge:
            #tasks_to_syndicate = []
            async for task in self.miner_challenge.execute_challenge(miner, batches):
                # TODO tolerate a failure to persist?
                await self.challenge_repository.add_task(task)
                logger.info("Received task response from miner", extra={'miner': miner.axon_info})

                #if not task.has_error:
                #    tasks_to_syndicate.append(task)
            # TODO: Send to API if OK

        logger.info("Miner Challenges complete.")

    async def _make_batch(self, prediction_interval: PredictionInterval, net_uid: int):
        metagraph = await self.subtensor.metagraph(net_uid)
        hotkeys_ss58 = metagraph.hotkeys
        batch_id = uuid.uuid4()
        return AlphaSellChallengeBatch(batch_id, datetime.now(UTC), net_uid, prediction_interval, hotkeys_ss58)


async def run_forever(wallet: Wallet, subtensor: AsyncSubtensor, db_url: str):

    engine = create_async_engine(db_url)
    challenge_repository = DatabaseAlphaSellChallengeRepository(engine)
    dendrite = bt.Dendrite(wallet)
    miner_client = AlphaSellMinerClient(dendrite)

    from patrol.validation.config import DASHBOARD_BASE_URL, ENABLE_DASHBOARD_SYNDICATION, PATROL_METAGRAPH, ALPHA_SELL_PREDICTION_WINDOW_BLOCKS
    dashboard_client = HttpDashboardClient(wallet, DASHBOARD_BASE_URL) if ENABLE_DASHBOARD_SYNDICATION else None

    miner_challenge = AlphaSellMinerChallenge(miner_client, dashboard_client)

    process = await AlphaSellMinerChallengeProcess.create(
        challenge_repository, miner_challenge, subtensor, PATROL_METAGRAPH,
        interval_window_blocks=ALPHA_SELL_PREDICTION_WINDOW_BLOCKS
    )

    while True:
        try:
            await process.challenge_miners()
        except Exception as ex:
            logger.exception("Unexpected error")
        finally:
            await asyncio.sleep(3600)

async def run(wallet: Wallet, subtensor: AsyncSubtensor, db_url: str):
    if subtensor:
        await run_forever(wallet, subtensor, db_url)
    else:
        from patrol.validation.config import ARCHIVE_SUBTENSOR
        async with AsyncSubtensor(ARCHIVE_SUBTENSOR) as st:
            await run_forever(wallet, st, db_url)


def start_process(wallet: Wallet, subtensor: AsyncSubtensor | None = None, db_url: str | None = None):
    def run_async():
        from patrol.validation.config import DB_URL
        asyncio.run(run(wallet, subtensor, db_url if db_url else DB_URL))

    process = multiprocessing.Process(target=run_async, daemon=True)
    process.start()
    return process


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        my_wallet = Wallet(name="vali", hotkey="vali", path=tmp)
        my_wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        start_process(my_wallet)
