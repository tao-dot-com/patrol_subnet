import typing
import bittensor as bt
from dataclasses import dataclass, field
from typing import Optional, Union, List

@dataclass(slots=True)
class TransferEvidence:
    rao_amount: int
    block_number: int

@dataclass(slots=True)
class StakeEvidence:
    block_number: int
    rao_amount: int
    destination_net_uid: Optional[int] = field(default=None)
    source_net_uid: Optional[int] = field(default=None)
    alpha_amount: Optional[int] = field(default=None)
    delegate_hotkey_source: Optional[str] = field(default=None)
    delegate_hotkey_destination: Optional[str] = field(default=None)

    def __post_init__(self):
        if self.block_number > 4920351:
            if self.destination_net_uid is None and self.source_net_uid is None:
                raise ValueError("Either destination_net_uid or source_net_uid must be provided.")
        if self.delegate_hotkey_source is None and self.delegate_hotkey_destination is None:
            raise ValueError("Either delegate_hotkey_source or delegate_hotkey_destination must be provided.")

@dataclass(slots=True)
class Edge:
    coldkey_source: str
    coldkey_destination: str
    category: str
    type: str
    evidence: Union[TransferEvidence, StakeEvidence]
    coldkey_owner: Optional[str] = field(default=None)

@dataclass(slots=True)
class Node:
    id: str
    type: str
    origin: str

@dataclass(slots=True)
class GraphPayload:
    nodes: List[Node]
    edges: List[Edge]

class PatrolSynapse(bt.Synapse):
    """
    A simple event graph protocol that inherits from bt.Synapse.
    This protocol handles event graph request and response communication between
    the miner and the validator.
    """

    target: typing.Optional[str] = field(default=None)
    target_block_number: typing.Optional[int] = field(default=None)
    max_block_number: typing.Optional[int] = field(default=None)

    subgraph_output: typing.Optional[GraphPayload] = field(default=None)
