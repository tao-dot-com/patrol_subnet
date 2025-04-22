from abc import ABC, abstractmethod
from patrol.validation.scoring import MinerScore

class DashboardClient(ABC):
    @abstractmethod
    async def send_score(self, score: MinerScore):
        pass