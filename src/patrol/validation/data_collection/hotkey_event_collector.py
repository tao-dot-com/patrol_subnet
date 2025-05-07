from patrol.chain_data.event_processor import EventProcessor
from patrol.validation.block_checkpoint import BlockCheckpoint
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.event_store_repository import EventStoreRepository, ChainEvent


class HotkeyEventCollector:
    def __init__(self, chain_reader: ChainReader,
                 event_store: EventStoreRepository,
                 block_checkpoint: BlockCheckpoint,
                 event_processor: EventProcessor = None,
                 block_batch_size: int = 100
     ):
        self._chain_reader = chain_reader
        self._event_processor = event_processor
        self._event_store = event_store
        self._block_checkpoint = block_checkpoint
        self._block_batch_size = block_batch_size

    async def collect_hotkey_ownership_events(self):

        start_block = await self._block_checkpoint.find_latest_processed_block("hotkey_event")
        max_block   = start_block + self._block_batch_size
        current_block = await self._chain_reader.get_current_block()

        end_block = max(max_block, current_block)

        for block_number in range(start_block, end_block):
            events = await self._chain_reader.find_block_events(block_number)
            processed_events = map(self._process_event, events)
            await self._event_store.add_chain_events(processed_events)

    def _process_event(self, raw_event) -> ChainEvent:
        pass






