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
    overall_score_moving_average: float
    overall_score: float
    volume_score: float
    volume: int
    responsiveness_score: float
    response_time_seconds: float
    novelty_score: Optional[float]
    validation_passed: bool
    error_message: Optional[str]

    @property
    def miner(self) -> tuple[str, int]:
        return self.hotkey, self.uid

class MinerScoreRepository(ABC):

    @abstractmethod
    async def add(self, score: MinerScore):
        pass

    @abstractmethod
    async def find_latest_overall_scores(self, miner: tuple[str, int], batch_count: int = 19) -> float:
        pass

    @abstractmethod
    async def find_last_average_overall_scores(self) -> dict[tuple[str, int], float]:
        pass