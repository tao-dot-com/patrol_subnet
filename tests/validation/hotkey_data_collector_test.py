from unittest.mock import AsyncMock

from patrol.chain_data.event_processor import EventProcessor
from patrol.validation.block_checkpoint import BlockCheckpoint
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.data_collection.hotkey_event_collector import HotkeyEventCollector
from patrol.validation.event_store_repository import EventStoreRepository, ChainEvent


async def test_collect_events():
    chain_reader = AsyncMock(ChainReader)
    block_checkpoint = AsyncMock(BlockCheckpoint)
    event_store = AsyncMock(EventStoreRepository)
    event_store.add_event = AsyncMock()
    event_processor = AsyncMock(EventProcessor)

    chain_events = []
    #     ChainEvent(),
    #     ChainEvent(),
    #     ChainEvent(),
    #     ChainEvent(),
    # ]

    async def mock_async_generator():
        for event in chain_events:
            yield event

    chain_reader.read_events = AsyncMock(return_value=mock_async_generator())
    block_checkpoint.find_latest_processed_block = AsyncMock(return_value=3_000_000)

    hotkey_event_collector = HotkeyEventCollector(chain_reader, event_store, block_checkpoint, event_processor, 100)

    await hotkey_event_collector.collect_hotkey_ownership_events()

    event_store.add_event.assert_called_once_with(chain_events[0])
    block_checkpoint.set_checkpoint.assert_called_once_with("foo", 3_000_100)
