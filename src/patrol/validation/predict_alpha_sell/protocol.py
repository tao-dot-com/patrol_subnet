from dataclasses import dataclass

import bittensor as bt
from typing import Optional

from patrol.validation.predict_alpha_sell import TransactionType


@dataclass(frozen=True)
class AlphaSellPrediction:
    wallet_hotkey_ss58: str
    wallet_coldkey_ss58: str
    transaction_type: TransactionType
    predicted_unstake_total: float


@dataclass(frozen=True)
class PredictionInterval:
    start_block: int
    end_block: int

class AlphaSellSynapse(bt.Synapse):
    batch_id: str
    task_id: str
    subnet_uid: int
    wallet_hotkeys_ss58: list[str]
    prediction_interval: Optional[PredictionInterval] = None
    predictions: Optional[list[AlphaSellPrediction]] = None

