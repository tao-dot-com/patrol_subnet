from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Iterable


@dataclass(frozen=True)
class ChainEvent:
    created_at: datetime
    edge_category: str
    block_number: int
    edge_type: str
    coldkey_destination: str
    coldkey_source: Optional[str] = None
    coldkey_owner: Optional[str] = None
    rao_amount: Optional[int] = None
    destination_net_uid: Optional[int] = None
    source_net_uid: Optional[int] = None
    alpha_amount: Optional[int] = None
    delegate_hotkey_source: Optional[str] = None
    delegate_hotkey_destination: Optional[str] = None


class EventStoreRepository(ABC):
    @abstractmethod
    async def add_chain_events(self, events: Iterable[ChainEvent]):
        pass

    @abstractmethod
    async def exists(self, chain_event):
        pass

