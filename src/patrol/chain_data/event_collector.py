import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, Optional
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.validation import hooks
from patrol.validation.config import DB_URL
from patrol.validation.persistence import Base
from patrol.validation.persistence.event_store_repository import DatabaseEventScoreRepository
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.event_processor import EventProcessor
from sqlalchemy.ext.asyncio import create_async_engine

_MIN_BLOCK_NUMBER = 3_014_342 

logger = logging.getLogger(__name__)


class EventCollector:
    def __init__(
        self,
        event_fetcher: EventFetcher,
        event_processor: EventProcessor,
        event_repository: DatabaseEventScoreRepository,
        sync_interval: int = 12,  # Default to 12 seconds (one block time)
        batch_size: int = 25
    ):
        self.event_fetcher = event_fetcher
        self.event_processor = event_processor
        self.event_repository = event_repository
        self.min_block_number = _MIN_BLOCK_NUMBER
        self.batch_size = batch_size

    async def _fetch_and_store_events(self, start_block: int, end_block: int) -> None:
        """
        Fetch events for a range of blocks and store them in the database.
        """
        logger.info(f"Fetching events from block {start_block} to {end_block}")
        
        # Get the block numbers we need to fetch
        block_numbers = list(range(start_block, end_block + 1))
        
        # Fetch events using the EventFetcher
        events_by_block = await self.event_fetcher.fetch_all_events(
            block_numbers, 
            batch_size=self.batch_size
        )
        
        if not events_by_block:
            logger.info(f"No events found in blocks {start_block} to {end_block}")
            return

        # Process events using the EventProcessor
        processed_events = []
        for block_num, events in events_by_block.items():
            # Process this block's events
            block_events = await self.event_processor.process_event_data({block_num: events})
            if block_events:
                processed_events.extend(block_events)
        
        # Convert processed events to database format
        event_data_list = []
        for event in processed_events:
            try:
                # Convert from the event processor format to database format
                event_data = self._convert_to_db_format(event)
                event_data_list.append(event_data)
            except Exception as e:
                logger.error(f"Error converting event to database format: {e}")
                continue
        
        # Store events in the database
        if event_data_list:
            try:
                await self.event_repository.add_events(event_data_list)
                logger.info(f"Stored {len(event_data_list)} events from blocks {start_block} to {end_block}")
            except Exception as e:
                logger.error(f"Error storing events in database: {e}")


    def _convert_to_db_format(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an event from the processor format to the database format.
        """
        # Extract evidence details
        evidence = event.get('evidence', {})
        
        # Determine evidence type
        evidence_type = "transfer" if "destination_net_uid" not in evidence else "stake"
        
        db_event = {
            "created_at": datetime.now(),
            "node_id": event.get("node_id", f"node_{event.get('coldkey_source')}"),
            "node_type": event.get("node_type", "account"),
            "node_origin": event.get("node_origin", "bittensor"),
            "coldkey_source": event.get("coldkey_source"),
            "coldkey_destination": event.get("coldkey_destination"),
            "edge_category": event.get("category"),
            "edge_type": event.get("type"),
            "coldkey_owner": event.get("coldkey_owner"),
            "evidence_type": evidence_type,
            "block_number": evidence.get("block_number"),
            "rao_amount": evidence.get("rao_amount")
        }
        
        # Add stake-specific fields if this is a stake event
        if evidence_type == "stake":
            db_event.update({
                "destination_net_uid": evidence.get("destination_net_uid"),
                "source_net_uid": evidence.get("source_net_uid"),
                "alpha_amount": evidence.get("alpha_amount"),
                "delegate_hotkey_source": evidence.get("delegate_hotkey_source"),
                "delegate_hotkey_destination": evidence.get("delegate_hotkey_destination")
            })
        
        return db_event
    

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

    event_repository = DatabaseEventScoreRepository(engine)
    
    # Create and start the syncer
    event_collector = EventCollector(
        event_fetcher=fetcher,
        event_processor=processor,
        event_repository=event_repository,
        sync_interval=12 
    )
    
    await event_collector._fetch_and_store_events(
        start_block=_MIN_BLOCK_NUMBER+10, end_block=_MIN_BLOCK_NUMBER+12
    )


if __name__ == "__main__":
    asyncio.run(main())
