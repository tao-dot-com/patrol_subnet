import uuid
from datetime import timedelta, datetime, UTC
from unittest.mock import AsyncMock

import pytest

from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeBatch, PredictionInterval, \
    TransactionType, AlphaSellPrediction, AlphaSellEventRepository, AlphaSellChallengeMiner
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellValidator
from patrol.validation.scoring import MinerScoreRepository


@pytest.fixture
def batch():
    return AlphaSellChallengeBatch(
        batch_id=uuid.uuid4(),
        subnet_uid=12, prediction_interval=PredictionInterval(100, 120),
        hotkeys_ss58=["alice", "bob"],
        created_at=datetime.now(UTC),
    )

def make_task(batch_id: uuid.UUID, predictions: list[AlphaSellPrediction]):
    return AlphaSellChallengeTask(
        batch_id=batch_id,
        task_id=uuid.uuid4(),
        created_at=datetime.now(UTC) - timedelta(days=1),
        miner=AlphaSellChallengeMiner("miner_1", "miner", 2),
        predictions=predictions,
    )

async def test_validate_exact_predictions(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 100.0),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 200.0),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": 100, "bob": 200}

    alpha_sell_validator = AlphaSellValidator()

    mean_square = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert mean_square == 1.0

async def test_validate_where_no_movements_exist(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 100),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 200),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 1 / (1 + (100 ** 2 + 200 ** 2) / 2)

async def test_validate_where_no_predictions_made(batch):

    predictions=[]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": 100, "bob": 200}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 1 / (1 + (100 ** 2 + 200 ** 2) / 2)
