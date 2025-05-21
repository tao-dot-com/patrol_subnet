import os
import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import AlphaSellChallenge, PredictionInterval, AlphaSellPrediction, \
    TransactionType


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
        await conn.execute(text("DELETE FROM alpha_sell_challenge"))
        await conn.commit()
    return pgsql_engine


async def test_add_challenge(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    now = datetime.now(UTC)

    challenge = AlphaSellChallenge(
        uuid.uuid4(),
        uuid.uuid4(),
        now,
        42, PredictionInterval(100, 120),
        ["alice", "bob", "carol"],
        [
            AlphaSellPrediction("alice", "alice_ck", TransactionType.UNSTAKE, 25.0),
            AlphaSellPrediction("carol", "carol_ck", TransactionType.UNSTAKE, 15.0),
        ],
        9.7
    )

    await repository.add(challenge)

    async with clean_pgsql_engine.connect() as conn:
        challenge_results = await conn.execute(text("SELECT * FROM alpha_sell_challenge"))
        assert challenge_results.rowcount == 1
        challenge_result = [dict(row._mapping) for row in challenge_results][0]

    assert challenge_result["batch_id"] == str(challenge.batch_id)
    assert challenge_result["task_id"] == str(challenge.task_id)
    assert challenge_result["subnet_uid"] == challenge.subnet_uid
    assert challenge_result["created_at"] == challenge.created_at
    assert challenge_result["prediction_interval_start"] == challenge.prediction_interval.start_block
    assert challenge_result["prediction_interval_end"] == challenge.prediction_interval.end_block
    assert challenge_result["hotkeys_ss58_json"] == ["alice", "bob", "carol"]
    assert challenge_result["response_time"] == 9.7

    async with clean_pgsql_engine.connect() as conn:
        prediction_results = await conn.execute(text("SELECT * FROM alpha_sell_prediction"))
        assert prediction_results.rowcount == 2
        all_results = [dict(row._mapping) for row in prediction_results]
        alice_prediction_result = all_results[0]
        carol_prediction_result = all_results[1]

    assert alice_prediction_result["task_id"] == str(challenge.task_id)
    assert alice_prediction_result["amount"] == 25.0
    assert alice_prediction_result["hotkey"] == "alice"

    assert carol_prediction_result["task_id"] == str(challenge.task_id)
    assert carol_prediction_result["amount"] == 15.0
    assert carol_prediction_result["hotkey"] == "carol"
