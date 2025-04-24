import datetime
import logging
import time
from dataclasses import asdict
from typing import Optional
from uuid import UUID

import aiohttp
from bittensor_wallet import Wallet

from pydantic import BaseModel

from patrol.validation.dashboard import DashboardClient
from patrol.validation.scoring import MinerScore

logger = logging.getLogger(__name__)

class _MinerScore(BaseModel):
    batch_id: UUID
    created_at: datetime
    uid: int
    hotkey: str
    coldkey: str
    volume: int
    volume_score: float
    response_time_seconds: float
    response_time_score: float
    overall_score: float
    overall_moving_average_score: float
    is_valid: bool
    error_message: Optional[str] = None

    model_config = {
        "arbitrary_types_allowed": True,
        "ser_json_datetime": "iso8601",  # optional for timedelta fields
        "ser_json_uuid": "str"
    }

    @classmethod
    def from_score(cls, score: MinerScore):
        return cls(
            uid=score.uid,
            batch_id=score.batch_id,
            created_at=score.created_at,
            coldkey=score.coldkey,
            hotkey=score.hotkey,
            volume=score.volume, volume_score=score.volume_score,
            response_time_seconds=score.response_time_seconds, response_time_score=score.responsiveness_score,
            overall_score=score.overall_score, overall_moving_average_score=score.overall_score_moving_average,
            is_valid=score.validation_passed,
            error_message=score.error_message
        )

class HttpDashboardClient(DashboardClient):

    def __init__(self, wallet: Wallet, dashboard_score_base_url: str):
        self._wallet = wallet
        self._dashboard_score_base_url = dashboard_score_base_url

    async def send_score(self, score: MinerScore):

        nonce = int(time.time())
        signature = self._wallet.hotkey.sign(str(nonce).encode())

        token = f"{self._wallet.hotkey.ss58_address}:{nonce}:{signature.hex()}"


        async with aiohttp.ClientSession() as session:
            async with session.put(
                    url=f"{self._dashboard_score_base_url}/patrol/dashboard/api/miner-scores/{score.id}",
                    data=_MinerScore.from_score(score).model_dump_json(exclude_none=False),
                    headers={"Content-Type": "application/json", "authorization": f"Bearer {token}"}
            ) as response:
                if response.ok:
                    logger.info("Sent score OK", extra=asdict(score))
                else:
                    logger.warning("Failed to send score %s", response.status, extra=asdict(score))
