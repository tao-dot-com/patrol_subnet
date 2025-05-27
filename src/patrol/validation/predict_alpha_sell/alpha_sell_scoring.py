from datetime import datetime, UTC

from patrol.constants import TaskType
from patrol.validation.chain.chain_utils import ChainUtils
from patrol.validation.dashboard import DashboardClient
from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeRepository, \
    AlphaSellEventRepository, AlphaSellChallengeBatch, TransactionType
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellValidator
from patrol.validation.scoring import MinerScore, MinerScoreRepository


class AlphaSellScoring:

    def __init__(
            self, challenge_repository: AlphaSellChallengeRepository,
            miner_score_repository: MinerScoreRepository,
            chain_utils: ChainUtils,
            alpha_sell_event_repository: AlphaSellEventRepository,
            alpha_sell_validator: AlphaSellValidator,
            dashboard_client: DashboardClient | None,
    ):
        self.challenge_repository = challenge_repository
        self.miner_score_repository = miner_score_repository
        self.chain_utils = chain_utils
        self.alpha_sell_event_repository = alpha_sell_event_repository
        self.alpha_sell_validator = alpha_sell_validator
        self.dashboard_client = dashboard_client

    async def score_miners(self):
        upper_block = (await self.chain_utils.get_current_block()) - 1
        for scorable_challenge_batch in await self.challenge_repository.find_scorable_challenges(upper_block):
            await self._score_batch(scorable_challenge_batch)

    async def _score_batch(self, batch: AlphaSellChallengeBatch):
        stake_removals = await self.alpha_sell_event_repository.find_aggregate_stake_movement_by_hotkey(
            subnet_id=batch.subnet_uid,
            lower_block=batch.prediction_interval.start_block, upper_block=batch.prediction_interval.end_block,
            transaction_type=TransactionType.STAKE_REMOVED
        )

        scorable_tasks = await self.challenge_repository.find_tasks(batch.batch_id)

        for task in scorable_tasks:
            await self._score_task(task, stake_removals)

    async def _score_task(self, task: AlphaSellChallengeTask, stake_removals: dict):

        accuracy = self.alpha_sell_validator.score_miner_accuracy(task, stake_removals)
        miner_score = self._make_miner_score(task, accuracy)

        await self.miner_score_repository.add(miner_score)

        if self.dashboard_client:
            await self.dashboard_client.send_score(miner_score)


    def _make_miner_score(self, task: AlphaSellChallengeTask, accuracy: float) -> MinerScore:
        responsiveness_score = 2 / (2 + task.response_time_seconds)
        accuracy_score = accuracy # FIXME: this is wrong

        overall_score = (9 * accuracy_score + responsiveness_score) / 10

        return MinerScore(
            id=task.task_id, batch_id=task.batch_id, created_at=datetime.now(UTC),
            uid=task.miner.uid,
            coldkey=task.miner.coldkey,
            hotkey=task.miner.hotkey,
            responsiveness_score=responsiveness_score,
            accuracy_score=accuracy_score,
            volume=0,
            volume_score=0.0,
            response_time_seconds=task.response_time_seconds,
            novelty_score=0.0,
            validation_passed=True,
            error_message=None,
            task_type=TaskType.PREDICT_ALPHA_SELL,
            overall_score=overall_score,
            overall_score_moving_average=0.0,
        )

