import os
import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellPrediction, \
    TransactionType, AlphaSellChallengeBatch, AlphaSellChallengeTask


@pytest.fixture
def pgsql_engine():
    url = os.getenv("TEST_POSTGRESQL_URL", "postgresql+asyncpg://patrol:password@localhost:5432/patrol")
    migrate_db(url)
    engine = create_async_engine(url)
    return engine

@pytest.fixture
async def clean_pgsql_engine(pgsql_engine):
    async with pgsql_engine.connect() as conn:
        await conn.execute(text("DELETE FROM alpha_sell_prediction"))
        await conn.execute(text("DELETE FROM alpha_sell_challenge_task"))
        await conn.execute(text("DELETE FROM alpha_sell_challenge_batch"))
        await conn.commit()
    return pgsql_engine


async def test_add_challenge(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    now = datetime.now(UTC)

    batch = AlphaSellChallengeBatch(
        uuid.uuid4(),
        now,
        42, PredictionInterval(100, 120),
        ["alice", "bob", "carol"],
    )

    await repository.add(batch)

    async with clean_pgsql_engine.connect() as conn:
        challenge_results = await conn.execute(text("SELECT * FROM alpha_sell_challenge_batch"))
        assert challenge_results.rowcount == 1
        challenge_result = [dict(row._mapping) for row in challenge_results][0]

    assert challenge_result["id"] == str(batch.batch_id)
    assert challenge_result["subnet_uid"] == batch.subnet_uid
    assert challenge_result["created_at"] == batch.created_at
    assert challenge_result["prediction_interval_start"] == batch.prediction_interval.start_block
    assert challenge_result["prediction_interval_end"] == batch.prediction_interval.end_block
    assert challenge_result["hotkeys_ss58_json"] == batch.hotkeys_ss58


async def test_add_challenge_task(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    now = datetime.now(UTC)

    batch = AlphaSellChallengeBatch(
        uuid.uuid4(),
        now,
        42, PredictionInterval(100, 120),
        ["alice", "bob", "carol"],
    )
    await repository.add(batch)

    task = AlphaSellChallengeTask(
        batch_id=batch.batch_id,
        task_id=uuid.uuid4(),
        created_at=now,
        miner=("miner", 1),
        predictions=[
            AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 25.0),
            AlphaSellPrediction("carol", "carol_ck", TransactionType.STAKE_REMOVED, 15.0),
        ],
        response_time_seconds=9.7,
    )

    await repository.add_task(task)

    async with clean_pgsql_engine.connect() as conn:
        task_results = await conn.execute(text("SELECT * FROM alpha_sell_challenge_task"))
        assert task_results.rowcount == 1
        task_result = [dict(row._mapping) for row in task_results][0]

    assert task_result["id"] == str(task.task_id)
    assert task_result["batch_id"] == str(task.batch_id)
    assert task_result["created_at"] == task.created_at
    assert task_result["miner_hotkey"] == task.miner[0]
    assert task_result["miner_uid"] == task.miner[1]
    assert task_result["response_time"] == 9.7

    async with clean_pgsql_engine.connect() as conn:
        prediction_results = await conn.execute(text("SELECT * FROM alpha_sell_prediction"))
        assert prediction_results.rowcount == 2
        all_results = [dict(row._mapping) for row in prediction_results]
        alice_prediction_result = all_results[0]
        carol_prediction_result = all_results[1]

    assert alice_prediction_result["task_id"] == str(task.task_id)
    assert alice_prediction_result["amount"] == 25.0
    assert alice_prediction_result["hotkey"] == "alice"

    assert carol_prediction_result["task_id"] == str(task.task_id)
    assert carol_prediction_result["amount"] == 15.0
    assert carol_prediction_result["hotkey"] == "carol"
