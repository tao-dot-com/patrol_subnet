from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TransferEvidence:
    rao_amount: int
    block_number: int

@dataclass
class StakeEvidence:
    block_number: int
    rao_amount: int
    destination_net_uid: int = None
    source_net_uid: int = None
    alpha_amount: Optional[int] = None
    delegate_hotkey_source: Optional[str] = None
    delegate_hotkey_destination: Optional[str] = None

    def __post_init__(self):
        if self.destination_net_uid is None and self.source_net_uid is None:
            raise ValueError("Either destination_net_uid or source_net_uid must be provided.")
        if self.delegate_hotkey_source is None and self.delegate_hotkey_destination is None:
            raise ValueError("Either delegate_hotkey_source or delegate_hotkey_destination must be provided.")

@dataclass
class Edge:
    coldkey_source: str
    coldkey_destination: str
    category: str
    type: str
    evidence: TransferEvidence | StakeEvidence
    coldkey_owner: Optional[str] = None

@dataclass
class Node:
    id: str
    type: str
    origin: str

@dataclass
class GraphPayload:
    nodes: List[Node]
    edges: List[Edge]

