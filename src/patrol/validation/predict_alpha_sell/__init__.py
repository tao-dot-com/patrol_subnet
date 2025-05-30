from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import Optional


class TransactionType(Enum):
    STAKE_REMOVED = "StakeRemoved"
    STAKE_ADDED = "StakeAdded"
    STAKE_MOVED = "StakeMoved"

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
    predictions: list[AlphaSellPrediction]
    has_error: bool = False
    error_message: Optional[str] = None

class AlphaSellChallengeRepository(ABC):
    @abstractmethod
    async def add(self, challenge: AlphaSellChallengeBatch):
        pass

    @abstractmethod
    async def add_task(self, challenge: AlphaSellChallengeTask):
        pass

    @abstractmethod
    async def find_scorable_challenges(self, upper_block: int) -> list[AlphaSellChallengeBatch]:
        pass

    @abstractmethod
    async def find_tasks(self, batch_id: UUID) -> list[AlphaSellChallengeTask]:
        pass

    @abstractmethod
    async def find_earliest_prediction_block(self):
        pass

    @abstractmethod
    async def mark_task_scored(self, task_id, session):
        pass


@dataclass(frozen=True)
class ChainStakeEvent:
    created_at: datetime
    block_number: int
    event_type: TransactionType
    rao_amount: int
    coldkey: str
    from_net_uid: Optional[int] = None
    to_net_uid: Optional[int] = None
    to_hotkey: Optional[str] = None
    from_hotkey: Optional[str] = None
    alpha_amount: Optional[int] = None

    @classmethod
    def stake_added(cls, created_at: datetime, block_number: int, rao_amount: int, alpha_amount: int, net_uid: int, coldkey: str, hotkey: str):
        return cls(
            created_at=created_at,
            block_number=block_number,
            event_type=TransactionType.STAKE_ADDED,
            rao_amount=rao_amount,
            alpha_amount=alpha_amount,
            to_net_uid=net_uid,
            coldkey=coldkey,
            to_hotkey=hotkey
        )

    @classmethod
    def stake_removed(cls, created_at: datetime, block_number: int, rao_amount: int, alpha_amount: int, net_uid: int, coldkey: str, hotkey: str):
        return cls(
            created_at=created_at,
            block_number=block_number,
            event_type=TransactionType.STAKE_REMOVED,
            rao_amount=rao_amount,
            alpha_amount=alpha_amount,
            from_net_uid=net_uid,
            coldkey=coldkey,
            from_hotkey=hotkey
        )

    @classmethod
    def stake_moved(cls, created_at: datetime, block_number: int, rao_amount: int, from_net_uid: int, to_net_uid: int, coldkey: str, from_hotkey: str, to_hotkey: str):
        return cls(
            created_at=created_at,
            block_number=block_number,
            event_type=TransactionType.STAKE_MOVED,
            rao_amount=rao_amount,
            from_net_uid=from_net_uid,
            to_net_uid=to_net_uid,
            coldkey=coldkey,
            from_hotkey=from_hotkey,
            to_hotkey=to_hotkey
        )

class AlphaSellEventRepository(ABC):
    @abstractmethod
    async def add(self, events: list[ChainStakeEvent]):
        pass

    @abstractmethod
    async def find_aggregate_stake_movement_by_hotkey(self, subnet_id, lower_block, upper_block, transaction_type: TransactionType) -> dict[str, int]:
        pass

    @abstractmethod
    async def find_most_recent_block_collected(self):
        pass

    @abstractmethod
    async def delete_events_before_block(self, earliest_block):
        pass
