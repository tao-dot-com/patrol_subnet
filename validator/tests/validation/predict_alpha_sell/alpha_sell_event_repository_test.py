import os
from datetime import datetime, UTC

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.persistence import migrate_db
from patrol.validation.predict_alpha_sell import ChainStakeEvent, TransactionType
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository
from patrol_common import WalletIdentifier


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
    event = ChainStakeEvent.stake_removed(datetime.now(UTC), 5000000, 500, 1000, 71, "coldkey1", "hotkey1")
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add([event])

    async with clean_pgsql_engine.connect() as conn:
        row = await conn.execute(text("SELECT * FROM alpha_sell_event"))
        assert row.rowcount == 1
        result = [dict(it._mapping) for it in row][0]
        assert result["created_at"] == event.created_at
        assert result["block_number"] == event.block_number
        assert result["event_type"] == event.event_type.name
        assert result["coldkey"] == event.coldkey
        assert result["from_hotkey"] == event.from_hotkey
        assert result["to_hotkey"] is None
        assert result["rao_amount"] == event.rao_amount
        assert result["from_net_uid"] == event.from_net_uid
        assert result["to_net_uid"] == event.to_net_uid
        assert result["alpha_amount"] == event.alpha_amount


async def test_add_event_when_alpha_not_present(clean_pgsql_engine):
    event = ChainStakeEvent.stake_removed(datetime.now(UTC), 5000000, 500, None, 72, "coldkey1", "hotkey1")
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add([event])

    async with clean_pgsql_engine.connect() as conn:
        row = await conn.execute(text("SELECT * FROM alpha_sell_event"))
        result = [dict(it._mapping) for it in row][0]
        assert result["alpha_amount"] is None


async def test_find_aggregate_stake_movement_by_hotkey(clean_pgsql_engine):
    events = [
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000000, 400, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000001, 500, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000001, 600, 1000, 72, "coldkey1", "hotkey2"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000010, 700, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000010, 800, 1000, 70, "coldkey2", "hotkey4"),
    ]
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add(events)

    stake_removed_events = await repository.find_aggregate_stake_movement_by_wallet(72, 5000000, 5000001, TransactionType.STAKE_REMOVED)
    assert stake_removed_events.keys() == {WalletIdentifier('coldkey1', 'hotkey1'), WalletIdentifier('coldkey1', 'hotkey2')}
    assert stake_removed_events[WalletIdentifier('coldkey1', 'hotkey1')] == 400 + 500
    assert stake_removed_events[WalletIdentifier('coldkey1', 'hotkey2')] == 600


async def test_find_most_recent_block(clean_pgsql_engine):
    events = [
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000000, 400, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000010, 800, 1000, 70, "coldkey2", "hotkey4"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000001, 500, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000010, 700, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000001, 600, 1000, 72, "coldkey1", "hotkey2"),
    ]
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add(events)

    most_recent_block = await repository.find_most_recent_block_collected()
    assert most_recent_block == 5000010


async def test_find_most_recent_block_in_empty_database(clean_pgsql_engine):
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)

    most_recent_block = await repository.find_most_recent_block_collected()
    assert most_recent_block is None

async def test_prune_events(clean_pgsql_engine):
    events = [
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000000, 400, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000001, 800, 1000, 70, "coldkey2", "hotkey4"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000002, 500, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000003, 700, 1000, 72, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_removed(datetime.now(UTC), 5000004, 600, 1000, 72, "coldkey1", "hotkey2"),
    ]
    repository = DataBaseAlphaSellEventRepository(clean_pgsql_engine)
    await repository.add(events)

    deleted_count = await repository.delete_events_before_block(5000002)
    assert deleted_count == 2

    async with clean_pgsql_engine.connect() as conn:
        min_block = await conn.execute(text("SELECT DISTINCT(block_number) FROM alpha_sell_event"))
        assert min_block.rowcount == 3
        assert set(min_block.scalars().all()) == {5000002, 5000003, 5000004}
