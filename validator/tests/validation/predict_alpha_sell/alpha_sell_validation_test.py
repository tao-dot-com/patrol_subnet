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
        scoring_batch=100
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

async def test_validate_exact_predictions_with_wallet_values_of_0_tao(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 0),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 0),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): 0, WalletIdentifier("bob_ck", "bob"): 0}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert total_score == approx(2.0, 0.0001)


async def test_validate_exact_predictions_with_wallet_values_of_1_tao(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(1E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(1E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(1E9), WalletIdentifier("bob_ck", "bob"): int(1E9)}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert total_score == approx(2.6, 0.05)


async def test_validate_exact_predictions_with_wallet_values_of_10_tao(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(10E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(10E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(10E9), WalletIdentifier("bob_ck", "bob"): int(10E9)}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert total_score == approx(4.0, 0.05)


async def test_validate_exact_predictions_with_wallet_values_of_1000_tao(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(1000E9)),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, int(1000E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(1000E9), WalletIdentifier("bob_ck", "bob"): int(1000E9)}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert total_score == approx(8.0, 0.05)


@pytest.mark.parametrize("predicted", [int(49E9),int(151E9)])
async def test_validate_predictions_off_by_just_greater_than_50_percent(batch, predicted):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, predicted),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(100E9)}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert total_score == 0.0


@pytest.mark.parametrize("predicted", [int(51E9),int(149E9)])
async def test_validate_predictions_off_by_just_less_than_50_percent(batch, predicted):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, predicted),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(100E9)}

    alpha_sell_validator = AlphaSellValidator()

    total_score = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert 0.0 < total_score < 0.2


async def test_validate_where_no_movements_exist(batch):

    predictions=[
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, int(0.25E9)),
    ]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 0.75

async def test_validate_where_no_predictions_made(batch):

    predictions=[]
    task = make_task(batch.batch_id, predictions)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): int(1E9), WalletIdentifier("bob_ck", "bob"): int(2E9)}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 0.0

async def test_validate_failed_task(batch):

    predictions=[]
    task = make_task(batch.batch_id, predictions, has_error=True)

    score_repo = AsyncMock(MinerScoreRepository)
    score_repo.find_latest_overall_scores.return_value = []

    stake_removals = {WalletIdentifier("alice_ck", "alice"): 100, WalletIdentifier("bob_ck", "bob"): 200}

    alpha_sell_validator = AlphaSellValidator()

    accuracy = alpha_sell_validator.score_miner_accuracy(task, stake_removals)
    assert accuracy == 0.0
