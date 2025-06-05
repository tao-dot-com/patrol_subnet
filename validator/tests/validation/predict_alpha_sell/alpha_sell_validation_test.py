import uuid
from datetime import timedelta, datetime, UTC
from unittest.mock import AsyncMock

import pytest
from pytest import approx

from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeBatch, PredictionInterval, \
    TransactionType, AlphaSellPrediction, AlphaSellChallengeMiner, WalletIdentifier
from patrol.validation.predict_alpha_sell.alpha_sell_scoring import AlphaSellValidator
from patrol.validation.scoring import MinerScoreRepository


@pytest.fixture
def batch():
    return AlphaSellChallengeBatch(
        batch_id=uuid.uuid4(),
        subnet_uid=12, prediction_interval=PredictionInterval(100, 120),
        wallets=[WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob")],
        created_at=datetime.now(UTC),
    )

def make_task(batch_id: uuid.UUID, predictions: list[AlphaSellPrediction], has_error: bool = False):
    return AlphaSellChallengeTask(
        batch_id=batch_id,
        task_id=uuid.uuid4(),
        created_at=datetime.now(UTC) - timedelta(days=1),
        miner=AlphaSellChallengeMiner("miner_1", "miner", 2),
        predictions=predictions,
        has_error=has_error,
    )

async def test_validate_exact_predictions(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(100E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(200E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": int(100E9), "bob": int(200E9)}

    alpha_sell_validator = AlphaSellValidator()

    mean_square = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert mean_square == 1.0

async def test_validate_predictions_off_by_99_percent(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(1E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(398E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": int(100E9), "bob": int(200E9)}

    alpha_sell_validator = AlphaSellValidator()

    mean_square = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert 0.01 < mean_square < 0.04


async def test_validate_predictions_off_by_100_percent(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(0E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(400E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": int(100E9), "bob": int(200E9)}

    alpha_sell_validator = AlphaSellValidator()

    mean_square = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert mean_square == approx(0.0, abs=0.02)

async def test_validate_predictions_off_by_105_percent(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(0E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(410E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": int(100E9), "bob": int(200E9)}

    alpha_sell_validator = AlphaSellValidator()

    mean_square = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert mean_square == 0.0

async def test_validate_where_no_movements_exist(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(0.5E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(1E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 0.375

async def test_validate_where_no_predictions_made(batch):

    predictions=[]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": int(1E9), "bob": int(2E9)}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == approx(0.63, rel=0.05)

async def test_validate_failed_task(batch):

    predictions=[]
    task = make_task(batch.batch_id, predictions, has_error=True)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {"alice": 100, "bob": 200}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 0.0
