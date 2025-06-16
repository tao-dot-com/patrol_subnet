from abc import ABC, abstractmethod
from patrol.validation.scoring import MinerScore

class DashboardClient(ABC):
    @abstractmethod
    async def send_scores(self, score: list[MinerScore]):
        pass