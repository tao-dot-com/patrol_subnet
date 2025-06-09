import uuid
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Optional, Iterable
from datetime import datetime

from patrol.validation import TaskType


@dataclass(frozen=True)
class ValidationResult:
    validated: bool
    message: str
    volume: int

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
    task_type: TaskType
    error_message: Optional[str] = None
    accuracy_score: Optional[float] = None
    scoring_batch: Optional[int] = None

    @property
    def miner(self) -> tuple[str, int]:
        return self.hotkey, self.uid


class MinerScoreRepository(ABC):

    @abstractmethod
    async def add(self, score: MinerScore, session = None):
        pass

    @abstractmethod
    async def find_latest_overall_scores(self, miner: tuple[str, int], task_type: TaskType, batch_count: int = 19) -> Iterable[float]:
        pass

    @abstractmethod
    async def find_last_average_overall_scores(self, task_type: TaskType) -> dict[tuple[str, int], float]:
        pass

    @abstractmethod
    async def find_latest_stake_prediction_overall_scores(self) -> dict[tuple[str, int], float]:
        pass
