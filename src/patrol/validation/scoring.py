from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class MinerScore(frozen=True):

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
    error_msg: Optional[str]

class MinerScoreRepository:

    @abstractmethod
    async def add(self, score: MinerScore):

        pass

    @abstractmethod
    async def find(self):
        # need to only retrieve the most recent hotkey/coldkey for a UID. 
        pass