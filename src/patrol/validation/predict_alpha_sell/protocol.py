from uuid import UUID

import bittensor as bt
from typing import Optional

from pydantic import field_validator

from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellPrediction


class AlphaSellSynapse(bt.Synapse):
    batch_id: str
    task_id: str
    subnet_uid: int
    wallet_hotkeys_ss58: list[str]
    prediction_interval: Optional[PredictionInterval] = None
    predictions: Optional[list[AlphaSellPrediction]] = None

    # class Config:
    #     json_encoders = {
    #         UUID: lambda uuid: str(uuid)
    #     }

    # model_config = {
    #     "json_encoders": {
    #         UUID: lambda uuid: str(uuid)
    #     }
    # }


