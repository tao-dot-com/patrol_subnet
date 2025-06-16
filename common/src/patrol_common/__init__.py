from dataclasses import dataclass
from enum import Enum


class TransactionType(Enum):
    STAKE_REMOVED = "StakeRemoved"
    STAKE_ADDED = "StakeAdded"
    STAKE_MOVED = "StakeMoved"


@dataclass(frozen=True)
class WalletIdentifier:
    coldkey: str
    hotkey: str


@dataclass(frozen=True)
class AlphaSellPrediction:
    wallet_hotkey_ss58: str
    wallet_coldkey_ss58: str
    transaction_type: TransactionType
    amount: int


@dataclass(frozen=True)
class PredictionInterval:
    start_block: int
    end_block: int
