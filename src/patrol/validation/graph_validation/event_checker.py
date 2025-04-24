
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from sqlalchemy import select
from typing import Any, List, Dict

from patrol.validation.persistence.event_store_repository import _ChainEvent


class EventChecker:

    def __init__(self, engine: AsyncEngine):
        self.LocalAsyncSession = async_sessionmaker(bind=engine)

    async def check_events_by_hash(self, event_data_list: List[Dict[str, Any]]) -> List[Dict]:
        """
        Check if events exist in the database by their hash.
        
        Args:
            event_data_list: List of event data dictionaries
            
        Returns:
            The number of events that don't exist in the database
        """
        async with self.LocalAsyncSession() as session:
            # Convert incoming events to EventStore objects with hashes
            events = [_ChainEvent.from_event(data) for data in event_data_list]
            
            # Extract hashes from incoming events
            event_hashes = [event.edge_hash for event in events]
            
            # Query database for matching hashes
            query = select(_ChainEvent.edge_hash).where(_ChainEvent.edge_hash.in_(event_hashes))
            result = await session.execute(query)
            fetched_rows = result.fetchall()
            existing_hashes = {row[0] for row in fetched_rows}
            
            # Find events that do exist in the database
            matched_events = [event_data_list[i] for i, event in enumerate(events) if event.edge_hash in existing_hashes]
            
            return matched_events
