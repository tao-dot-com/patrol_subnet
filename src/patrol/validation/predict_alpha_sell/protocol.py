from uuid import UUID

import bittensor as bt
from typing import Optional

from pydantic import field_validator

from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellPrediction, WalletIdentifier


class AlphaSellSynapse(bt.Synapse):
    batch_id: str
    task_id: str
    subnet_uid: int
    wallets: Optional[list[WalletIdentifier]] = None
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


