import uuid
from datetime import datetime, UTC, timedelta
from unittest.mock import AsyncMock, patch, ANY

from sqlalchemy.ext.asyncio import AsyncSession

from patrol.constants import TaskType
from patrol.validation.chain.chain_utils import ChainUtils
from patrol.validation.dashboard import DashboardClient
from patrol.validation.persistence.transaction_helper import TransactionHelper
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, AlphaSellEventRepository, \
    AlphaSellChallengeBatch, PredictionInterval, AlphaSellChallengeTask, AlphaSellChallengeMiner, \
    AlphaSellPrediction, TransactionType
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellValidator
from patrol.validation.predict_alpha_sell.alpha_sell_scoring import AlphaSellScoring, make_miner_score
from patrol.validation.scoring import MinerScoreRepository, MinerScore


@patch("patrol.validation.predict_alpha_sell.alpha_sell_scoring.datetime")
async def test_score_miner_tasks(mock_datetime: datetime):
    scoring_repository = AsyncMock(MinerScoreRepository)
    challenge_repository = AsyncMock(AlphaSellChallengeRepository)
    chain_utils = AsyncMock(ChainUtils)
    event_repository = AsyncMock(AlphaSellEventRepository)
    dashboard_client = AsyncMock(DashboardClient)

    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    mock_datetime.now.return_value = now

    task_created_at = datetime.now(UTC) - timedelta(hours=24)

    challenge_repository.find_scorable_challenges.return_value = [
        AlphaSellChallengeBatch(batch_id=batch_id, created_at=task_created_at, subnet_uid=42,
                                prediction_interval=PredictionInterval(100, 120), hotkeys_ss58=["alice", "bob"])
    ]

    task_id = uuid.uuid4()
    challenge_repository.find_tasks.return_value = [
        AlphaSellChallengeTask(batch_id=batch_id, task_id=task_id, created_at=task_created_at,
                               miner=AlphaSellChallengeMiner("miner", "miner_ck", 42),
                               predictions=[
                                   AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 100),
                                   AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 20),
                               ]
        )]

    chain_utils.get_current_block.return_value = 120
    event_repository.find_aggregate_stake_movement_by_hotkey.return_value = {
        "alice": 400
    }

    validator = AsyncMock(AlphaSellValidator)
    validator.score_miner_accuracy.return_value = 0.8

    transaction_helper = AsyncMock(TransactionHelper)
    mock_session = AsyncMock(AsyncSession)
    async def side_effect(func):
        await func(mock_session)

    transaction_helper.do_in_transaction = AsyncMock(side_effect=side_effect)

    scoring = AlphaSellScoring(
        challenge_repository, scoring_repository, chain_utils, event_repository, validator, dashboard_client,
        transaction_helper,
    )
    await scoring.score_miners()

    expected_accuracy_score = 0.8
    expected_overall_score = expected_accuracy_score

    score_1: MinerScore = scoring_repository.add.mock_calls[0].args[0]
    assert score_1.id == task_id
    assert score_1.batch_id == batch_id
    assert score_1.uid == 42
    assert score_1.coldkey == "miner_ck"
    assert score_1.hotkey == "miner"
    assert score_1.volume == 0
    assert score_1.novelty_score == 0.0
    assert score_1.responsiveness_score == 0.0
    assert score_1.created_at == now
    assert score_1.response_time_seconds == 0.0
    assert score_1.validation_passed
    assert score_1.error_message is None
    assert score_1.overall_score_moving_average == 0.0
    assert score_1.task_type == TaskType.PREDICT_ALPHA_SELL
    assert score_1.overall_score == expected_overall_score
    assert score_1.accuracy_score == expected_accuracy_score

    scoring_repository.add.assert_awaited_once_with(ANY, mock_session)
    challenge_repository.mark_task_scored.assert_awaited_once_with(task_id, mock_session)


def test_failed_task_score():
    task = AlphaSellChallengeTask(
        uuid.uuid4(), uuid.uuid4(), datetime.now(UTC),
        AlphaSellChallengeMiner("miner", "miner_ck", 42),
        predictions=[],
        has_error=True, error_message="Nope"
    )

    score = make_miner_score(task, 0)
    assert score.overall_score == 0
    assert score.accuracy_score == 0
    assert not score.validation_passed
    assert score.error_message == "Nope"