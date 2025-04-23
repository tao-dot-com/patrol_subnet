import hashlib
import json
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from sqlalchemy.orm import mapped_column, Mapped, MappedAsDataclass
from sqlalchemy import BigInteger, DateTime, or_, select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC
from patrol.validation.persistence import Base
import uuid
from typing import Any, Dict, List, Optional

def create_event_hash(event: Dict[str, Any]) -> str:
    """
    Creates a unique hash for an event based on its key properties.
    """
    # Select fields that make an event unique
    hash_fields = {
        "coldkey_source": event.get("coldkey_source"),
        "coldkey_destination": event.get("coldkey_destination"),
        "edge_category": event.get("edge_category") or event.get("category"),
        "edge_type": event.get("edge_type") or event.get("type"),
        "block_number": event.get("block_number"),
        "evidence_type": event.get("evidence_type"),
        "rao_amount": event.get("rao_amount")
    }
    
    # Add stake-specific fields if they exist
    if event.get("evidence_type") == "stake" or event.get("destination_net_uid") is not None:
        hash_fields.update({
            "destination_net_uid": event.get("destination_net_uid"),
            "source_net_uid": event.get("source_net_uid"),
            "delegate_hotkey_source": event.get("delegate_hotkey_source"),
            "delegate_hotkey_destination": event.get("delegate_hotkey_destination")
        })
    
    # Create a consistent string representation
    hash_string = json.dumps(hash_fields, sort_keys=True, default=str)
    
    # Create SHA-256 hash
    hash_object = hashlib.sha256(hash_string.encode())
    return hash_object.hexdigest()

class _EventStore(Base, MappedAsDataclass):
    __tablename__ = "event_store"

    # Primary key and metadata
    edge_hash: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    
    # Node fields
    node_id: Mapped[str]
    node_type: Mapped[str]
    node_origin: Mapped[str]
    
    # Edge fields
    coldkey_source: Mapped[str]
    coldkey_destination: Mapped[str]
    edge_category: Mapped[str]
    edge_type: Mapped[str]
    coldkey_owner: Mapped[Optional[str]]
    
    # Evidence fields - Common
    evidence_type: Mapped[str]  # "transfer" or "stake"
    block_number: Mapped[int]
    
    # TransferEvidence specific fields
    rao_amount: Mapped[int] = mapped_column(BigInteger)
    
    # StakeEvidence specific fields
    destination_net_uid: Mapped[Optional[int]]
    source_net_uid: Mapped[Optional[int]]
    alpha_amount: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    delegate_hotkey_source: Mapped[Optional[str]]
    delegate_hotkey_destination: Mapped[Optional[str]]
    
    @classmethod
    def from_event(cls, event):
        return cls(
            created_at=event.get('created_at', datetime.now(UTC)),
            node_id=event['node_id'],
            node_type=event['node_type'],
            node_origin=event['node_origin'],
            coldkey_source=event['coldkey_source'],
            coldkey_destination=event['coldkey_destination'],
            edge_category=event['edge_category'],
            edge_type=event['edge_type'],
            coldkey_owner=event.get('coldkey_owner'),
            evidence_type=event['evidence_type'],
            block_number=event['block_number'],
            rao_amount=event['rao_amount'],
            destination_net_uid=event.get('destination_net_uid'),
            source_net_uid=event.get('source_net_uid'),
            alpha_amount=event.get('alpha_amount'),
            delegate_hotkey_source=event.get('delegate_hotkey_source'),
            delegate_hotkey_destination=event.get('delegate_hotkey_destination'),
            edge_hash=create_event_hash(event)
        )
    
    @staticmethod
    def _to_utc(instant):
        """
        SQLite does not persist timezone info, so just set the timezone to UTC if the DB did not give us one.
        """
        return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)


class DatabaseEventStoreRepository:

    def __init__(self, engine: AsyncEngine):
        self.LocalAsyncSession = async_sessionmaker(bind=engine)

    async def add_events(self, event_data_list: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple blockchain events at once.
        
        Args:
            event_data_list: List of dictionaries, each containing event data
        """
        async with self.LocalAsyncSession() as session:
            for data in event_data_list:
                try:
                    # Create the event object with edge_hash as primary key
                    event = _EventStore.from_event(data)
                    session.add(event)
                    await session.flush()  # Flush to detect errors immediately
                except IntegrityError:
                    # This will catch primary key violations
                    await session.rollback()  # Rollback this specific operation

        # Commit all successful insertions
        await session.commit()

    async def find_by_coldkey(self, coldkey: str) -> List[Dict[str, Any]]:
        """
        Find events associated with a specific coldkey.
        
        Args:
            coldkey: The coldkey to search for
            
        Returns:
            List of events associated with the coldkey
        """
        async with self.LocalAsyncSession() as session:
            query = select(_EventStore).filter(
                or_(
                    _EventStore.coldkey_source == coldkey,
                    _EventStore.coldkey_destination == coldkey,
                )
            )
            result = await session.execute(query)
            return [self._to_dict(event) for event in result.scalars().all()]

    async def check_events_by_hash(self, event_data_list: List[Dict[str, Any]]) -> int:
        """
        Check if events exist in the database by their hash.
        
        Args:
            event_data_list: List of event data dictionaries
            
        Returns:
            The number of events that don't exist in the database
        """
        async with self.LocalAsyncSession() as session:
            # Convert incoming events to EventStore objects with hashes
            events = [_EventStore.from_event(**data) for data in event_data_list]
            
            # Extract hashes from incoming events
            event_hashes = [event.edge_hash for event in events]
            
            # Query database for matching hashes
            query = select(_EventStore.edge_hash).where(_EventStore.edge_hash.in_(event_hashes))
            result = await session.execute(query)
            existing_hashes = {row[0] for row in result.fetchall()}
            
            # Count events that don't exist in the database
            unmatched_count = sum(1 for event_hash in event_hashes if event_hash not in existing_hashes)
            
            return unmatched_count
