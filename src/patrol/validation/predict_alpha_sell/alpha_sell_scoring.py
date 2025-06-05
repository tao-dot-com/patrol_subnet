import asyncio
import dataclasses
import logging
import multiprocessing
import time
from datetime import datetime, UTC
from tempfile import TemporaryDirectory

from async_substrate_interface import AsyncSubstrateInterface
from bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.constants import TaskType
from patrol.validation.chain.chain_utils import ChainUtils
from patrol.validation.dashboard import DashboardClient
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository
from patrol.validation.persistence.miner_score_respository import DatabaseMinerScoreRepository
from patrol.validation.persistence.transaction_helper import TransactionHelper
from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeRepository, \
    AlphaSellEventRepository, AlphaSellChallengeBatch, TransactionType
from patrol.validation.scoring import MinerScore, MinerScoreRepository

logger = logging.getLogger(__name__)


def make_miner_score(task: AlphaSellChallengeTask, accuracy: float) -> MinerScore:
    #responsiveness_score = 2 / (2 + task.response_time_seconds)
    accuracy_score = accuracy # FIXME: this is wrong

    overall_score = accuracy_score # + responsiveness_score) / 10

    return MinerScore(
        id=task.task_id, batch_id=task.batch_id, created_at=datetime.now(UTC),
        uid=task.miner.uid,
        coldkey=task.miner.coldkey,
        hotkey=task.miner.hotkey,
        responsiveness_score=0.0,
        accuracy_score=accuracy_score,
        volume=0,
        volume_score=0.0,
        response_time_seconds=0.0,
        novelty_score=0.0,
        validation_passed=not task.has_error,
        error_message=task.error_message,
        task_type=TaskType.PREDICT_ALPHA_SELL,
        overall_score=overall_score,
        overall_score_moving_average=0.0,
    )


class AlphaSellValidator:

    def __init__(self, noise_floor: float = 1):
        self.noise_floor = noise_floor

    def score_miner_accuracy(self, task: AlphaSellChallengeTask, stake_removals: dict[str, int]) -> float:
        if task.has_error:
            return 0.0

        predictions_by_hotkey = {p.wallet_hotkey_ss58: p.amount for p in task.predictions}

        all_hotkeys = set(predictions_by_hotkey.keys() | stake_removals.keys())

        square_deltas = []

        for hk in all_hotkeys:
            predicted_rao = predictions_by_hotkey.get(hk, 0)
            predicted_tao = predicted_rao / 1e9

            actual_rao = stake_removals.get(hk, 0)
            actual_tao = actual_rao / 1e9

            relative_delta = ((predicted_tao - actual_tao) / (actual_tao + self.noise_floor)) ** 2
            square_deltas.append(relative_delta)

        if len(square_deltas) == 0:
            return 0.0

        mean_square_deltas = sum(square_deltas) / len(square_deltas)

        accuracy = max(0.0, 1.0 - mean_square_deltas)
        return accuracy


class AlphaSellScoring:

    def __init__(
            self, challenge_repository: AlphaSellChallengeRepository,
            miner_score_repository: MinerScoreRepository,
            chain_utils: ChainUtils,
            alpha_sell_event_repository: AlphaSellEventRepository,
            alpha_sell_validator: AlphaSellValidator,
            dashboard_client: DashboardClient | None,
            transaction_helper: TransactionHelper,
    ):
        self.challenge_repository = challenge_repository
        self.miner_score_repository = miner_score_repository
        self.chain_utils = chain_utils
        self.alpha_sell_event_repository = alpha_sell_event_repository
        self.alpha_sell_validator = alpha_sell_validator
        self.dashboard_client = dashboard_client
        self.transaction_helper = transaction_helper

    async def score_miners(self):
        upper_block = (await self.chain_utils.get_current_block()) - 1
        scorable_batches = await self.challenge_repository.find_scorable_challenges(upper_block)

        if len(scorable_batches) == 0:
            logger.info("No scorable batches found")

        for scorable_challenge_batch in scorable_batches:
            await self._score_batch(scorable_challenge_batch)

    async def _score_batch(self, batch: AlphaSellChallengeBatch):
        logger.info("Scoring batch [%s]", batch.batch_id)
        stake_removals = await self.alpha_sell_event_repository.find_aggregate_stake_movement_by_hotkey(
            subnet_id=batch.subnet_uid,
            lower_block=batch.prediction_interval.start_block, upper_block=batch.prediction_interval.end_block,
            transaction_type=TransactionType.STAKE_REMOVED
        )

        scorable_tasks = await self.challenge_repository.find_tasks(batch.batch_id)

        for task in scorable_tasks:
            await self._score_task(task, stake_removals)

        await self.challenge_repository.remove_if_fully_scored(batch.batch_id)

    async def _score_task(self, task: AlphaSellChallengeTask, stake_removals: dict):
        miner_log_context = dataclasses.asdict(task.miner)

        logger.info("Scoring task [%s]", task.task_id, extra=miner_log_context)
        accuracy = self.alpha_sell_validator.score_miner_accuracy(task, stake_removals)
        miner_score = make_miner_score(task, accuracy)

        async def add_score(session):
            await self.miner_score_repository.add(miner_score, session)
            await self.challenge_repository.mark_task_scored(task.task_id, session)

        await self.transaction_helper.do_in_transaction(add_score)

        logger.info("Scored miner", extra=dataclasses.asdict(miner_score))

        if self.dashboard_client:
            try:
                await self.dashboard_client.send_score(miner_score)
            except Exception:
                logger.exception("Error sending score to dashboard")


def start_scoring(wallet: Wallet, db_url: str, enable_dashboard_syndication: bool):

    async def start_scoring_async():
        from patrol.validation.config import DASHBOARD_BASE_URL, ARCHIVE_SUBTENSOR, SCORING_INTERVAL_SECONDS
        engine = create_async_engine(db_url, pool_pre_ping=True)

        challenge_repository = DatabaseAlphaSellChallengeRepository(engine)
        alpha_sell_event_repository = DataBaseAlphaSellEventRepository(engine)
        alpha_sell_validator = AlphaSellValidator()
        miner_score_repository = DatabaseMinerScoreRepository(engine)
        dashboard_client = HttpDashboardClient(wallet, DASHBOARD_BASE_URL) if enable_dashboard_syndication else None
        transaction_helper = TransactionHelper(engine)

        async with AsyncSubstrateInterface(ARCHIVE_SUBTENSOR) as substrate:
            chain_utils = ChainUtils(substrate)
            scoring = AlphaSellScoring(
                challenge_repository,
                miner_score_repository,
                chain_utils,
                alpha_sell_event_repository,
                alpha_sell_validator,
                dashboard_client,
                transaction_helper
            )

            go = True
            while go:
                try:
                    await scoring.score_miners()
                    await asyncio.sleep(SCORING_INTERVAL_SECONDS)
                except KeyboardInterrupt:
                    logger.info("Stopping alpha-sell scoring process")
                    go = False
                except Exception as ex:
                    logger.exception("Unexpected error")

            logger.info("Stopped alpha-sell scoring process")

    asyncio.run(start_scoring_async())

def start_scoring_process(wallet: Wallet, db_url: str, enable_dashboard_syndication: bool = False):
    process = multiprocessing.Process(target=start_scoring, name="Scoring", args=[wallet, db_url, enable_dashboard_syndication], daemon=True)
    process.start()
    return process
