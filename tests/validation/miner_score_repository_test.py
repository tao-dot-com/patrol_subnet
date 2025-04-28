import uuid
from datetime import datetime, UTC, timedelta

import pytest
from patrol.validation.persistence import Base
from patrol.validation.persistence.miner_score_respository import DatabaseMinerScoreRepository, _MinerScore
from patrol.validation.scoring import MinerScore
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text

@pytest.fixture
async def memory_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Close engine
    await engine.dispose()

@pytest.fixture
async def repository(memory_db_engine):
    """Create a DatabaseMinerScoreRepository with an in-memory database."""
    repository = DatabaseMinerScoreRepository(memory_db_engine)
    yield repository

async def test_add_score(repository, memory_db_engine):
    batch_id = uuid.uuid4()
    score_id = uuid.uuid4()
    now = datetime.now(UTC)

    miner_score = MinerScore(
        id=score_id,
        batch_id=batch_id,
        created_at=now,
        uid=42,
        coldkey="abcdef",
        hotkey="ghijkl",
        overall_score_moving_average=5.0,
        overall_score=10.0,
        volume=12,
        volume_score=4.5,
        responsiveness_score=2.4,
        response_time_seconds=4.5,
        novelty_score=3.5,
        validation_passed=False,
        error_message="Oh dear",
    )

    await repository.add(miner_score)

    async with async_sessionmaker(memory_db_engine)() as sess:
        results = await sess.scalars(select(_MinerScore))
        rows = results.all()

    assert len(rows) == 1
    score: _MinerScore = rows[0]
    assert score.id == str(score_id)
    assert score.batch_id == str(batch_id)
    assert score.created_at.replace(tzinfo=UTC) == now
    assert score.uid == 42
    assert score.coldkey == "abcdef"
    assert score.hotkey == "ghijkl"
    assert score.overall_score == 10.0
    assert score.volume == 12
    assert score.volume_score == 4.5
    assert score.responsiveness_score == 2.4
    assert score.response_time_seconds == 4.5
    assert score.novelty_score == 3.5
    assert score.validation_passed == False
    assert score.error_message == "Oh dear"

async def test_find_sum_of_previous_overall_scores(repository):
    batch_ids = [uuid.uuid4(), uuid.uuid4()]
    now = datetime.now(UTC)
    # add 2 scores for each batch
    for b in batch_ids:
        miner_score_1 = make_miner_score(uuid.uuid4(), b, now)
        await repository.add(miner_score_1)
        miner_score_2 = make_miner_score(uuid.uuid4(), b, now)
        await repository.add(miner_score_2)

    overall_scores = await repository.find_latest_overall_scores(("ghijkl", 42), 20)
    assert overall_scores == [10.0, 10.0, 10.0, 10.0]

async def test_find_sum_of_limited_previous_overall_scores(repository):
    batch_ids = [uuid.uuid4(), uuid.uuid4()]
    now = datetime.now(UTC)
    # add 2 scores for each batch
    for b in batch_ids:
        miner_score_1 = make_miner_score(uuid.uuid4(), b, now)
        await repository.add(miner_score_1)
        miner_score_2 = make_miner_score(uuid.uuid4(), b, now)
        await repository.add(miner_score_2)

    overall_scores = await repository.find_latest_overall_scores(("ghijkl", 42), 2)
    assert overall_scores == [10.0, 10.0]

async def test_find_last_average_overall_scores(repository):
    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    await repository.add(make_miner_score(
        uuid.uuid4(), batch_id, miner=("abc", 1),
        created_at = now - timedelta(minutes=10), overall_score_moving_average=5.0))
    await repository.add(make_miner_score(
        uuid.uuid4(), batch_id, miner=("abc", 1),
        created_at = now - timedelta(minutes=20), overall_score_moving_average=6.0))
    await repository.add(make_miner_score(
        uuid.uuid4(), batch_id, miner=("def", 1),
        created_at = now - timedelta(minutes=30), overall_score_moving_average=7.0))

    scores = await repository.find_last_average_overall_scores()
    assert scores == {
        ("abc", 1): 5.0,
        ("def", 1): 7.0,
    }


def make_miner_score(
        score_id: uuid.UUID, batch_id: uuid.UUID, created_at: datetime,
        miner: tuple[str, int] = ("ghijkl", 42),
        overall_score: float = 10.0,
        overall_score_moving_average: float = 10.0
):
    return MinerScore(
        id=score_id,
        batch_id=batch_id,
        created_at=created_at,
        uid=miner[1],
        coldkey="abcdef",
        hotkey=miner[0],
        overall_score=overall_score,
        overall_score_moving_average=overall_score_moving_average,
        volume=12,
        volume_score=4.5,
        responsiveness_score=2.4,
        response_time_seconds=4.5,
        novelty_score=3.5,
        validation_passed=False,
        error_message="Oh dear",
    )
