from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.persistence.alpha_sell_event_repository import DataBaseAlphaSellEventRepository
from patrol.validation.predict_alpha_sell import AlphaSellEventRepository, ChainStakeEvent
from patrol.validation.predict_alpha_sell.stake_event_collector import StakeEventCollector

@pytest.mark.skip(reason="This test is not working yet.")
async def test_collect_real_events():
    runtime_versions = RuntimeVersions()
    versions = {k: v for k, v in runtime_versions.versions.items() if int(k) >= 258}

    substrate_client = SubstrateClient(versions, "wss://archive.chain.opentensor.ai:443/")
    await substrate_client.initialize()

    chain_reader = ChainReader(substrate_client, runtime_versions)

    engine = create_async_engine("postgresql+asyncpg://patrol:password@localhost:5432/patrol")
    event_repository = DataBaseAlphaSellEventRepository(engine)
    event_collector = StakeEventCollector(chain_reader, event_repository, AsyncMock())

    await event_collector.collect_events()


async def test_collect_events():
    chain_reader = AsyncMock(ChainReader)
    events_collected = [
        ChainStakeEvent.stake_removed(datetime.now(), 1000000, 100, 1000, 1, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_added(datetime.now(), 1000001, 100, 1000, 1, "coldkey1", "hotkey1"),
        ChainStakeEvent.stake_moved(datetime.now(), 1000002, 100, 1, 2, "coldkey1", "hotkey1", "hotkey2"),
    ]

    chain_reader.find_stake_events.return_value = events_collected
    chain_reader.get_last_finalized_block.return_value = 1000003

    event_repository = AsyncMock(AlphaSellEventRepository)
    event_collector = StakeEventCollector(chain_reader, event_repository, AsyncMock())
    event_repository.find_most_recent_block_collected.return_value = 1000000 - 500

    await event_collector.collect_events()

    event_repository.add.assert_awaited_once_with(events_collected)

