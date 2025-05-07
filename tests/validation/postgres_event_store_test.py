import os
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.event_store_repository import ChainEvent
from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository

@pytest.fixture
def pgsql_engine():
    url = os.getenv("TEST_POSTGRESQL_URL", "postgresql+asyncpg://patrol:password@localhost:5432/patrol")
    migrate_db(url)
    engine = create_async_engine(url)
    return engine

@pytest.fixture
async def clean_pgsql_engine(pgsql_engine):
    async with pgsql_engine.connect() as conn:
        await conn.execute(text("DELETE FROM event_store"))
        await conn.commit()
    return pgsql_engine

async def test_add_chain_events(clean_pgsql_engine):
    repository = DatabaseEventStoreRepository(clean_pgsql_engine)

    block_numbers = range(4_000_000, 4_000_100)

    def chain_events():
        for block_number in block_numbers:
            yield make_chain_event(block_number)

    await repository.add_chain_events(chain_events())

    async with clean_pgsql_engine.connect() as conn:
        results = await conn.execute(text("select count(*) from event_store"))
        assert results.scalar() == 100


def make_chain_event(block_number: int):
    return ChainEvent(
        created_at=datetime.now(UTC),
        edge_type="foo",
        edge_category="bar",
        coldkey_destination="5Dftedwsaggfas0dfgi9sdf",
        block_number=block_number
    )