from dataclasses import dataclass
from uuid import UUID

import bittensor as bt
from typing import Optional


@dataclass
class AlphaSellPrediction:
    wallet_hotkey_ss58: str
    wallet_coldkey_ss58: str
    predicted_unstake_total: float


class AlphaSellSynapse(bt.Synapse):
    batch_id: str
    task_id: str
    subnet_uid: int
    wallet_hotkeys_ss58: list[str]
    prediction_interval_blocks: int
    predictions: Optional[list[AlphaSellPrediction]] = None

