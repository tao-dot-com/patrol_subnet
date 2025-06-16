from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Optional


@dataclass(frozen=True)
class ChainEvent:
    edge_category: str
    edge_type: str
    block_number: int
    coldkey_destination: str
    coldkey_source: Optional[str] = None
    created_at: datetime = datetime.now(UTC)
