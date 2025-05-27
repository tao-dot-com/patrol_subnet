from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Optional

class TransactionType(Enum):
    STAKE_REMOVED = "StakeRemoved"

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
class AlphaSellChallengeMiner:
    hotkey: str
    coldkey: str
    uid: int


@dataclass(frozen=True)
class AlphaSellChallengeBatch:
    batch_id: UUID
    created_at: datetime
    subnet_uid: int
    prediction_interval: PredictionInterval
    hotkeys_ss58: list[str]

@dataclass(frozen=True)
class AlphaSellChallengeTask:
    batch_id: UUID
    task_id: UUID
    created_at: datetime
    miner: AlphaSellChallengeMiner
    response_time_seconds: float
    predictions: list[AlphaSellPrediction]

class AlphaSellChallengeRepository(ABC):
    @abstractmethod
    async def add(self, challenge):
        pass

    @abstractmethod
    async def find_scorable_challenges(self, upper_block: int) -> list[AlphaSellChallengeBatch]:
        pass

    @abstractmethod
    async def find_tasks(self, batch_id: UUID) -> list[AlphaSellChallengeTask]:
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

    @abstractmethod
    async def find_aggregate_stake_movement_by_hotkey(self, subnet_id, lower_block, upper_block, transaction_type: TransactionType) -> dict[str, int]:
        pass
