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
    response_time_seconds: float


class AlphaSellChallengeRepository(ABC):
    @abstractmethod
    async def add(self, challenge):
        pass

@dataclass(frozen=True)
class ChainStakeEvent:
    created_at: datetime
    block_number: int
    event_type: str
    coldkey: str
    hotkey: str
    rao_amount: int
    net_uid: int
    alpha_amount: Optional[int] = None

class AlphaSellEventRepository(ABC):
    @abstractmethod
    async def add(self, events: list[ChainStakeEvent]):
        pass