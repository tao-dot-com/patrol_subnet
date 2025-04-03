from dataclasses import dataclass
from typing import List

@dataclass
class TransferEvidence:
    amount: int
    block_number: int

@dataclass
class StakeEvidence:
    amount: int
    block_number: int
    netuid: int

@dataclass
class Edge:
    source: str
    destination: str
    type: str
    evidence: TransferEvidence | StakeEvidence

@dataclass
class Node:
    id: str
    type: str
    origin: str

@dataclass
class GraphPayload:
    nodes: List[Node]
    edges: List[Edge]