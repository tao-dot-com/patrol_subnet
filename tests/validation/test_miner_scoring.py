import uuid
from unittest.mock import AsyncMock

import pytest
from patrol.validation.miner_scoring import MinerScoring, normalize_scores
from patrol.validation.graph_validation.errors import ErrorPayload
from patrol.protocol import GraphPayload, Node, Edge, TransferEvidence
from patrol.constants import Constants
from patrol.validation.scoring import MinerScoreRepository


@pytest.fixture
def mock_miner_score_repository():
    return AsyncMock(MinerScoreRepository)

@pytest.fixture
def scoring(mock_miner_score_repository):
    return MinerScoring(mock_miner_score_repository)

def test_calculate_volume_score_valid(scoring):
    payload = GraphPayload(
        nodes=[Node(id="A", type="wallet", origin="bittensor")],
        edges=[Edge(
            coldkey_source="A",
            coldkey_destination="B",
            category="balance",
            type="transfer",
            evidence=TransferEvidence(rao_amount=10, block_number=1)
        )]
    )
    score = scoring.calculate_volume_score(payload)
    assert 0 < score <= 1.0

def test_calculate_volume_score_error_payload(scoring):
    score = scoring.calculate_volume_score({"error": "bad format"})
    assert score == 0.0

def test_calculate_responsiveness_score(scoring):
    fast = scoring.calculate_responsiveness_score(0.5)
    assert fast > 0.5

    slow = scoring.calculate_responsiveness_score(Constants.MAX_RESPONSE_TIME)
    assert slow == 0.0

async def test_calculate_score_error(scoring):
    error = ErrorPayload(message="Missing field")
    result = await scoring.calculate_score(
        uid=42,
        coldkey="ck",
        hotkey="hk",
        payload=error,
        response_time=2.0,
        batch_id=uuid.uuid4(),
        moving_average_denominator=20
    )
    assert result.validation_passed is False
    assert result.error_message == "Missing field"
    assert result.overall_score == 0.0

async def test_calculate_score_success(scoring):
    payload = GraphPayload(
        nodes=[Node(id="A", type="wallet", origin="bittensor")],
        edges=[Edge(
            coldkey_source="A",
            coldkey_destination="B",
            category="balance",
            type="transfer",
            evidence=TransferEvidence(rao_amount=10, block_number=1)
        )]
    )
    result = await scoring.calculate_score(
        uid=1,
        coldkey="ck1",
        hotkey="hk1",
        payload=payload,
        response_time=0.2,
        batch_id=uuid.uuid4(),
        moving_average_denominator=20,
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