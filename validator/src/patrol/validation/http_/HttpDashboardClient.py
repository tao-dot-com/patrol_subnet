from datetime import datetime
import logging
import time
from dataclasses import asdict
from typing import Optional
from uuid import UUID

import aiohttp
from bittensor_wallet import Wallet

from pydantic import BaseModel

from patrol.validation import TaskType
from patrol.validation.dashboard import DashboardClient
from patrol.validation.scoring import MinerScore

logger = logging.getLogger(__name__)

class _MinerScore(BaseModel):
    batch_id: UUID
    created_at: datetime
    uid: int
    hotkey: str
    coldkey: str
    stake_added_score: float
    stake_removed_score: float
    overall_score: float
    overall_moving_average_score: float
    is_valid: bool
    task_type: TaskType
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
            stake_added_score=score.stake_addition_score,
            stake_removed_score=score.stake_removal_score,
            overall_score=score.overall_score,
            overall_moving_average_score=score.overall_score_moving_average,
            is_valid=score.validation_passed,
            task_type=score.task_type,
            error_message=score.error_message
        )

class HttpDashboardClient(DashboardClient):

    def __init__(self, wallet: Wallet, dashboard_score_base_url: str):
        self._wallet = wallet
        self._dashboard_score_base_url = dashboard_score_base_url

    async def send_scores(self, scores: list[MinerScore]):

        nonce = int(time.time())
        signature = self._wallet.hotkey.sign(str(nonce).encode())

        token = f"{self._wallet.hotkey.ss58_address}:{nonce}:{signature.hex()}"


        async with aiohttp.ClientSession(base_url=self._dashboard_score_base_url) as session:
            for score in scores:
                async with session.put(
                        url=f"/patrol/dashboard/api/miner-scores/{score.id}",
                        data=_MinerScore.from_score(score).model_dump_json(exclude_none=False),
                        headers={"Content-Type": "application/json", "authorization": f"Bearer {token}"}
                ) as response:
                    if response.ok:
                        logger.info("Sent score OK", extra=asdict(score))
                    else:
                        logger.warning("Failed to send score %s", response.status, extra=asdict(score))
