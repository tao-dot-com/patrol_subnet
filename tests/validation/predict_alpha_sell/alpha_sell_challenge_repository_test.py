import dataclasses
import json
import os
import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellPrediction, \
    TransactionType, AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellChallengeMiner, WalletIdentifier


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
        [WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")],
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
    assert challenge_result["wallets_json"] == [dataclasses.asdict(it) for it in batch.wallets]



async def test_add_challenge_task(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    now = datetime.now(UTC)

    batch = AlphaSellChallengeBatch(
        uuid.uuid4(),
        now,
        42, PredictionInterval(100, 120),
        [WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")],
    )
    await repository.add(batch)

    task = AlphaSellChallengeTask(
        batch_id=batch.batch_id,
        task_id=uuid.uuid4(),
        created_at=now,
        miner=AlphaSellChallengeMiner("miner_hk", "miner_ck", 1),
        predictions=[
            AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 25.0),
            AlphaSellPrediction("carol", "carol_ck", TransactionType.STAKE_REMOVED, 15.0),
        ],
    )

    await repository.add_task(task)

    async with clean_pgsql_engine.connect() as conn:
        task_results = await conn.execute(text("SELECT * FROM alpha_sell_challenge_task"))
        assert task_results.rowcount == 1
        task_result = [dict(row._mapping) for row in task_results][0]

    assert task_result["id"] == str(task.task_id)
    assert task_result["batch_id"] == str(task.batch_id)
    assert task_result["created_at"] == task.created_at
    assert task_result["miner_hotkey"] == task.miner.hotkey
    assert task_result["miner_coldkey"] == task.miner.coldkey
    assert task_result["miner_uid"] == task.miner.uid
    assert task_result["response_time"] == 0.0

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


async def test_find_tasks_for_batch(clean_pgsql_engine):
    batch_id_1 = uuid.uuid4()
    batch_id_2 = uuid.uuid4()

    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    batch_1 = AlphaSellChallengeBatch(batch_id_1, datetime.now(UTC), 42, PredictionInterval(100, 120), [
        WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")
    ])
    await repository.add(batch_1)

    batch_2 = AlphaSellChallengeBatch(batch_id_2, datetime.now(UTC), 42, PredictionInterval(100, 120), [
        WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")
    ])
    await repository.add(batch_2)

    task_1_a = AlphaSellChallengeTask(
            batch_id_1, uuid.uuid4(), datetime.now(UTC), AlphaSellChallengeMiner("miner_hk", "miner_ck", 1), predictions=[
               AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
               AlphaSellPrediction("bob", "b", TransactionType.STAKE_REMOVED, 25),
            ])
    await repository.add_task(task_1_a)

    task_1_b = AlphaSellChallengeTask(
            batch_id_1, uuid.uuid4(), datetime.now(UTC), AlphaSellChallengeMiner("miner_hk", "miner_ck", 2), predictions=[
               AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
               AlphaSellPrediction("bob", "b", TransactionType.STAKE_REMOVED, 25),
            ])
    await repository.add_task(task_1_b)

    task_2 = AlphaSellChallengeTask(
        batch_id_2, uuid.uuid4(), datetime.now(UTC), AlphaSellChallengeMiner("miner_hk", "miner_ck", 1), predictions=[
            AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
            AlphaSellPrediction("bob", "b", TransactionType.STAKE_REMOVED, 25),
        ])
    await repository.add_task(task_2)

    found_tasks = await repository.find_tasks(batch_id_1)
    assert len(found_tasks) == 2
    assert task_1_a in found_tasks
    assert task_1_b in found_tasks
    assert task_2 not in found_tasks


async def test_find_scorable_challenge_batches(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)

    batch_id_1 = uuid.uuid4()
    batch_id_2 = uuid.uuid4()

    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    batch_1 = AlphaSellChallengeBatch(batch_id_1, datetime.now(UTC), 42, PredictionInterval(111, 120), [
        WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")
    ])
    await repository.add(batch_1)

    batch_2 = AlphaSellChallengeBatch(batch_id_2, datetime.now(UTC), 42, PredictionInterval(121, 130), [
        WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")
    ])
    await repository.add(batch_2)

    challenges = await repository.find_scorable_challenges(130)
    assert len(challenges) == 0

    await repository.mark_batches_ready_for_scoring([batch_1.batch_id, batch_2.batch_id])
    challenges = await repository.find_scorable_challenges(130)
    assert len(challenges) == 2
    assert batch_1 in challenges
    assert batch_2 in challenges

    challenges = await repository.find_scorable_challenges(120)
    assert len(challenges) == 1
    assert batch_1 in challenges
    assert batch_2 not in challenges

async def test_find_earliest_prediction_block(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)

    await repository.add(AlphaSellChallengeBatch(
        uuid.uuid4(),
        datetime.now(UTC),
        42, PredictionInterval(100, 120),
        [WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")],
    ))
    await repository.add(AlphaSellChallengeBatch(
        uuid.uuid4(),
        datetime.now(UTC),
        42, PredictionInterval(115, 125),
        [WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")],
    ))

    earliest_block = await repository.find_earliest_prediction_block()
    assert earliest_block == 100

async def test_mark_task_scored(clean_pgsql_engine):
    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)

    batch_id = uuid.uuid4()

    repository = DatabaseAlphaSellChallengeRepository(clean_pgsql_engine)
    batch_1 = AlphaSellChallengeBatch(batch_id, datetime.now(UTC), 42, PredictionInterval(100, 120), [
        WalletIdentifier("a", "alice"), WalletIdentifier("b", "bob"), WalletIdentifier("c", "carol")
    ])
    await repository.add(batch_1)

    task_1 = AlphaSellChallengeTask(
        batch_id, uuid.uuid4(), datetime.now(UTC), AlphaSellChallengeMiner("miner_hk", "miner_ck", 1), predictions=[
            AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
            AlphaSellPrediction("bob", "b", TransactionType.STAKE_REMOVED, 25),
        ])
    await repository.add_task(task_1)

    task_2 = AlphaSellChallengeTask(
        batch_id, uuid.uuid4(), datetime.now(UTC), AlphaSellChallengeMiner("miner_hk", "miner_ck", 2), predictions=[
            AlphaSellPrediction("alice", "a", TransactionType.STAKE_REMOVED, 25),
            AlphaSellPrediction("bob", "b", TransactionType.STAKE_REMOVED, 25),
        ])
    await repository.add_task(task_2)

    scorable_tasks = await repository.find_tasks(batch_id)
    assert len(scorable_tasks) == 2

    async with async_sessionmaker(clean_pgsql_engine).begin() as session:
        await repository.mark_task_scored(task_1.task_id, session)

    scorable_tasks = await repository.find_tasks(batch_id)
    assert len(scorable_tasks) == 1
    assert task_1 not in scorable_tasks
    assert task_2 in scorable_tasks

