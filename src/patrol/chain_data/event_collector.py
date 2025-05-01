import asyncio
from collections import deque
import logging
import time
from typing import Any, Dict, Deque, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine

from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_processor import EventProcessor
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.validation import hooks
from patrol.validation.config import DB_URL
from patrol.validation.persistence import Base
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository
from patrol.constants import Constants
from patrol.validation.persistence.missed_blocks_repository import MissedBlocksRepository

logger = logging.getLogger(__name__)


class EventCollector:
    def __init__(
        self,
        event_fetcher: EventFetcher,
        event_processor: EventProcessor,
        event_repository: DatabaseEventStoreRepository,
        missed_blocks_repository: MissedBlocksRepository,
        sync_interval: int = 12,  # Default to 12 seconds (one block time)
        batch_size: int = 50,     # Current best batch size for querying without errors
        buffer_size: int = 5000   # Number of events to store in buffer before processing
    ):
        self.event_fetcher = event_fetcher
        self.event_processor = event_processor
        self.event_repository = event_repository
        self.missed_blocks_repository = missed_blocks_repository
        self.batch_size = batch_size
        self.buffer_size = buffer_size
        self.running = False
        self.last_synced_block = None
        self.sync_interval = sync_interval

    async def _fetch_and_store_events(self, start_block: int, end_block: int) -> None:
        """
        Fetch events for a range of blocks and store them in the database.
        """

        logger.info(f"Fetching events from block {start_block} to {end_block}")
        
        block_numbers = list(range(start_block, end_block + 1))

        queue = asyncio.Queue()
        missed_blocks = []
        blocks_without_events = []
        async def process_buffered_events(buffer: Deque[Tuple[int, Any]]) -> None:

            if not buffer:
                return
            
            to_process = dict(buffer)
            processed_batch = await self.event_processor.process_event_data(to_process)
            logger.info(f"Received and processed {len(processed_batch)} events.")
            
            event_data_list = []
            blocks_with_events = set()

            for event in processed_batch:
                event_data = self._convert_to_db_format(event)
                event_data_list.append(event_data)

                # Add the block number to blocks_with_events. Once its gone through the event processor we
                # can be sure it has at least 1 transfer or staking event.
                if 'block_number' in event_data:
                    blocks_with_events.add(event_data['block_number'])
            
            # Store events to DB
            if event_data_list:
                try:
                    await self.event_repository.add_events(event_data_list)
                    logger.info(f"Stored {len(event_data_list)} events from blocks {start_block} to {end_block}")
                except Exception as e:
                    logger.error(f"Error storing events in database: {e}")

            if len(to_process.keys()) != blocks_with_events:
                blocks_without_events.extend(
                    set(to_process.keys()) - blocks_with_events
                )

        async def consumer_event_queue() -> None:
            buffer: Deque[Tuple[int, Any]] = deque()

            while True:
                events = await queue.get()
                if events is None:
                    break

                buffer.extend(events.items())
                while len(buffer) >= self.buffer_size:
                    temp_buffer = deque(buffer.popleft() for _ in range(self.buffer_size))
                    await process_buffered_events(temp_buffer)

            await process_buffered_events(buffer)

        try:
            producer_task = asyncio.create_task(self.event_fetcher.stream_all_events(block_numbers, queue, missed_blocks, batch_size=self.batch_size))
            consumer_task = asyncio.create_task(consumer_event_queue())

            await asyncio.gather(producer_task, consumer_task)
        except Exception as e:
            logger.error(f"Error during event fetching/storing: {e}")
        finally:
            # Record any missed blocks
            if missed_blocks:
                logger.warning(f"Recording {len(missed_blocks)} missed blocks in range {start_block}-{end_block}")
                await self.missed_blocks_repository.add_missed_blocks(
                    missed_blocks,
                    error_message=f"Failed fetching blocks!"
                )
            if blocks_without_events:
                logger.warning(f"Recording {len(blocks_without_events)} blocks which don't have events.")
                await self.missed_blocks_repository.add_missed_blocks(
                    blocks_without_events,
                    error_message=f"Block does not contain transfer/staking events."
                )


    def _convert_to_db_format(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an event from the processor format to the database format.
        """
        evidence = event.get('evidence', {})
                
        db_event = {
            "created_at": datetime.now(),
            "coldkey_source": event.get("coldkey_source"),
            "coldkey_destination": event.get("coldkey_destination"),
            "edge_category": event.get("category"),
            "edge_type": event.get("type"),
            "coldkey_owner": event.get("coldkey_owner"),
            "block_number": evidence.get("block_number"),
            "rao_amount": evidence.get("rao_amount")
        }
        
        if db_event["edge_category"] == "staking":
            db_event.update({
                "destination_net_uid": evidence.get("destination_net_uid"),
                "source_net_uid": evidence.get("source_net_uid"),
                "alpha_amount": evidence.get("alpha_amount"),
                "delegate_hotkey_source": evidence.get("delegate_hotkey_source"),
                "delegate_hotkey_destination": evidence.get("delegate_hotkey_destination")
            })
        
        return db_event
    
    async def _sync_loop(self) -> None:
        """
        Main synchronization loop that runs continuously.
        """
        try:
            while self.running:
                start_time = time.time()
                
                # Get the current block number
                current_block = await self.event_fetcher.get_current_block()
                
                # Determine the start block for this sync
                if self.last_synced_block is None:
                    # Retrieve min block number from DB
                    start_block = await self.event_repository.get_highest_block_from_db()
                    # If no blocks in DB, default to configured min block number 
                    if start_block is None:
                        start_block = Constants.LOWER_BLOCK_LIMIT
                    else:
                        start_block += 1
                else:
                    start_block = self.last_synced_block + 1
                
                # Determine the end block for this sync (limit to reasonable batch size)
                max_blocks_per_sync = 1000
                end_block = min(current_block, start_block + max_blocks_per_sync)
                
                try:
                    # Fetch and store events for this range
                    await self._fetch_and_store_events(start_block, end_block)
                    self.last_synced_block = end_block
                    logger.info(f"Synced blocks {start_block} to {end_block}. Last synced block: {self.last_synced_block}")
                except Exception as e:
                    logger.error(f"Error during sync: {e}")
                
                # Calculate how long to wait before the next sync - adjusts dynamically based on 
                # num blocks left to ingest
                elapsed = time.time() - start_time
                wait_time = max(0, self.sync_interval - elapsed)
                
                logger.info(f"Sync completed in {elapsed:.2f}s. Waiting {wait_time:.2f}s before next sync...")
                await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Unexpected error in sync loop: {e}")
            self.running = False

    async def start(self) -> None:
        """
        Start the event collector.
        """
        if self.running:
            logger.warning("BlockchainEventSyncer is already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._sync_loop())
        logger.info(f"Started blockchain event collector.")

    async def stop(self) -> None:
        """
        Stop the blockchain event collector.
        """
        if not self.running:
            return
        
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Stopped blockchain event collector.")
    

async def create_tables(engine):
    """Create all database tables if they don't exist."""
    logger.info("Creating database tables if they don't exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created or confirmed to exist.")


async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Setup substrate client
    network_url = "wss://archive.chain.opentensor.ai:443/"
    versions = load_versions()
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
    await client.initialize()
    
    # Setup components
    fetcher = EventFetcher(substrate_client=client)
    coldkey_finder = ColdkeyFinder(client)
    processor = EventProcessor(coldkey_finder=coldkey_finder)
    
    # Setup database
    engine = create_async_engine(DB_URL, pool_pre_ping=True)
    hooks.invoke(hooks.HookType.ON_CREATE_DB_ENGINE, engine)

    # Create tables before using them
    await create_tables(engine)

    event_repository = DatabaseEventStoreRepository(engine)
    missed_blocks_repository = MissedBlocksRepository(engine)
    
    # Create and start the syncer
    event_collector = EventCollector(
        event_fetcher=fetcher,
        event_processor=processor,
        event_repository=event_repository,
        missed_blocks_repository=missed_blocks_repository,
        sync_interval=12 
    )
    
    await event_collector.start()
    
    # Run for a while
    try:
        await asyncio.sleep(300)
    finally:
        await event_collector.stop()


if __name__ == "__main__":
    asyncio.run(main())
