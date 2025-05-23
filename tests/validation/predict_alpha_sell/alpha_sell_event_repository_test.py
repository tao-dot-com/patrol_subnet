import os
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.persistence import migrate_db
from patrol.validation.predict_alpha_sell import ChainStakeEvent, TransactionType
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository

@pytest.fixture
def pgsql_engine():
    url = os.getenv("TEST_POSTGRESQL_URL", "postgresql+asyncpg://patrol:password@localhost:5432/patrol")
    migrate_db(url)
    engine = create_async_engine(url)
    return engine

@pytest.fixture
async def clean_pgsql_engine(pgsql_engine):
    async with pgsql_engine.connect() as conn:
        await conn.execute(text("DELETE FROM alpha_sell_event"))
        await conn.commit()
    return pgsql_engine

async def test_add_events(clean_pgsql_engine):
    event = ChainStakeEvent(datetime.now(UTC), 5000000, "StakeRemoved", "coldkey1", "hotkey1",500, 72, 1000)
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add([event])

    async with clean_pgsql_engine.connect() as conn:
        row = await conn.execute(text("SELECT * FROM alpha_sell_event"))
        assert row.rowcount == 1
        result = [dict(it._mapping) for it in row][0]
        assert result["created_at"] == event.created_at
        assert result["block_number"] == event.block_number
        assert result["event_type"] == event.event_type
        assert result["coldkey"] == event.coldkey
        assert result["hotkey"] == event.hotkey
        assert result["rao_amount"] == event.rao_amount
        assert result["net_uid"] == event.net_uid
        assert result["alpha_amount"] == event.alpha_amount


async def test_add_event_when_alpha_not_present(clean_pgsql_engine):
    event = ChainStakeEvent(datetime.now(UTC), 5000000, "StakeRemoved", "coldkey1", "hotkey1",500, 72, alpha_amount=None)
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add([event])

    async with clean_pgsql_engine.connect() as conn:
        row = await conn.execute(text("SELECT * FROM alpha_sell_event"))
        result = [dict(it._mapping) for it in row][0]
        assert result["alpha_amount"] is None


async def test_find_aggregate_stake_movement_by_hotkey(clean_pgsql_engine):
    events = [
        ChainStakeEvent(datetime.now(UTC), 5000000, "StakeRemoved", "coldkey1", "hotkey1", 400, 72, 1000),
        ChainStakeEvent(datetime.now(UTC), 5000001, "StakeRemoved", "coldkey1", "hotkey1", 500, 72, 1000),
        ChainStakeEvent(datetime.now(UTC), 5000001, "StakeRemoved", "coldkey1", "hotkey2", 600, 72, 1000),
        ChainStakeEvent(datetime.now(UTC), 5000010, "StakeRemoved", "coldkey1", "hotkey1", 700, 72, 1000),
        ChainStakeEvent(datetime.now(UTC), 5000010, "StakeRemoved", "coldkey2", "hotkey4", 800, 70, 1000),
    ]
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add(events)

    stake_removed_events = await repository.find_aggregate_stake_movement_by_hotkey(72, 5000000, 5000001, TransactionType.STAKE_REMOVED)
    assert stake_removed_events.keys() == {"hotkey1", "hotkey2"}
    assert stake_removed_events['hotkey1'] == 400 + 500
    assert stake_removed_events['hotkey2'] == 600
