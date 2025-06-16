import uuid
from unittest.mock import AsyncMock

import pytest

from patrol.validation import TaskType
from patrol.validation.miner_scoring import MinerScoring, normalize_scores
from patrol.validation.scoring import MinerScoreRepository, ValidationResult


@pytest.fixture
def mock_miner_score_repository():
    return AsyncMock(MinerScoreRepository)

@pytest.fixture
def scoring(mock_miner_score_repository):
    return MinerScoring(mock_miner_score_repository)

def test_calculate_volume_score_valid(scoring):
    score = scoring.calculate_volume_score(1200)
    assert 0 < score <= 1.0

def test_calculate_responsiveness_score(scoring):
    fast = scoring.calculate_responsiveness_score(0.5)
    assert fast > 0.5

    slow = scoring.calculate_responsiveness_score(10)
    assert slow < 0.2

async def test_calculate_score_error(scoring):
    error = ValidationResult(validated=False, message="Missing field", volume=0)
    result = await scoring.calculate_score(
        uid=42,
        coldkey="ck",
        hotkey="hk",
        validation_result=error,
        response_time=2.0,
        batch_id=uuid.uuid4(),
    )
    assert result.validation_passed is False
    assert result.error_message == "Missing field"
    assert result.overall_score == 0.0

async def test_calculate_score_success(scoring):
    validation_result = ValidationResult(validated=True, message="Pass", volume=100)
    result = await scoring.calculate_score(
        uid=1,
        coldkey="ck1",
        hotkey="hk1",
        validation_result=validation_result,
        response_time=0.2,
        batch_id=uuid.uuid4(),
    )
    assert result.validation_passed is True
    assert result.volume_score > 0
    assert result.overall_score > 0

def test_normalize_scores_empty():
    assert normalize_scores({}) == {}

def test_normalize_scores_same_values():
    scores = {1: 0.5, 2: 0.5}
    assert normalize_scores(scores) == [1.0, 1.0]

def test_normalize_scores_varied_values():
    scores = {1: 0.2, 2: 0.5, 3: 0.8}
    norm = normalize_scores(scores)
    assert isinstance(norm, dict)
    assert norm[1] == 0.0
    assert norm[3] == 1.0

async def test_miner_scoring_when_valid(mock_miner_score_repository):
    batch_id = uuid.uuid4()

    mock_miner_score_repository.find_latest_overall_scores = AsyncMock(
        return_value=[0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.9, 0.9, 0.9]
    )

    scoring = MinerScoring(mock_miner_score_repository, 10)
    result = ValidationResult(True, "", 1000)
    score = await scoring.calculate_score(72, "alice", "bob", result, 2, batch_id)

    assert score.volume_score == 0.5
    assert score.responsiveness_score == 0.5
    assert score.volume == 1000
    assert score.response_time_seconds == 2
    assert score.overall_score == 0.5
    assert score.overall_score_moving_average == (0.9 * 4 + 0.8 + 0.7 + 0.6 + 0.5) / 8
    assert score.uid == 72
    assert score.coldkey == "alice"
    assert score.hotkey == "bob"
    assert score.batch_id == batch_id
    assert score.task_type == TaskType.COLDKEY_SEARCH
    assert score.validation_passed
    assert score.error_message is None

