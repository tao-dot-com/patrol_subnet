import uuid
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass(frozen=True)
class MinerScore:
    id: uuid.UUID
    batch_id: uuid.UUID
    created_at: datetime
    uid: int
    coldkey: str
    hotkey: str
    overall_score: float
    volume_score: float
    volume: int
    responsiveness_score: float
    response_time_seconds: float
    novelty_score: Optional[float]
    validation_passed: bool
    error_message: Optional[str]

class MinerScoreRepository():

    @abstractmethod
    async def add(self, score: MinerScore):
        pass

    @abstractmethod
    async def find_by_batch_id(self, batch_id: uuid.UUID) -> list[MinerScore]:
        pass