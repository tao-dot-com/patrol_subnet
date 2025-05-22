import os
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.persistence import migrate_db
from patrol.validation.predict_alpha_sell import ChainStakeEvent
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
        assert result["alpha_amount"] == None
