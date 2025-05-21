from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Optional

class TransactionType(Enum):
    UNSTAKE = "UNSTAKE"

@dataclass(frozen=True)
class AlphaSellPrediction:
    wallet_hotkey_ss58: str
    wallet_coldkey_ss58: str
    transaction_type: TransactionType
    amount: float


@dataclass(frozen=True)
class PredictionInterval:
    start_block: int
    end_block: int


@dataclass(frozen=True)
class AlphaSellChallenge:
    batch_id: UUID
    task_id: UUID
    created_at: datetime
    subnet_uid: int
    prediction_interval: PredictionInterval
    hotkeys_ss58: list[str]
    predictions: list[AlphaSellPrediction]


class AlphaSellChallengeRepository(ABC):
    @abstractmethod
    def add(self, challenge):
        pass

@dataclass(frozen=True)
class ChainStakeEvent:
    created_at: datetime
    edge_category: str
    block_number: int
    edge_type: str
    coldkey_destination: Optional[str] = None
    coldkey_source: Optional[str] = None
    coldkey_owner: Optional[str] = None
    rao_amount: Optional[int] = None
    destination_net_uid: Optional[int] = None
    source_net_uid: Optional[int] = None
    alpha_amount: Optional[int] = None
    delegate_hotkey_source: Optional[str] = None
    delegate_hotkey_destination: Optional[str] = None