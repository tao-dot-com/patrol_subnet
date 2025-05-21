import bittensor as bt
from typing import Optional

from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellPrediction


class AlphaSellSynapse(bt.Synapse):
    batch_id: str
    task_id: str
    subnet_uid: int
    wallet_hotkeys_ss58: list[str]
    prediction_interval: Optional[PredictionInterval] = None
    predictions: Optional[list[AlphaSellPrediction]] = None

