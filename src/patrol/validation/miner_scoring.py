from typing import Dict, Any, List
import bittensor as bt
import math
import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.protocol import GraphPayload
from patrol.validation.graph_validation.errors import ErrorPayload
from patrol.validation.scoring import MinerScore
from patrol.constants import Constants

class MinerScoring:
    def __init__(self):
        self.importance = {
            'volume': 0.5,
            'responsiveness': 0.5,
        }

    def calculate_novelty_score(self, payload: Dict[str, Any]) -> float:
        # Placeholder for future implementation
        return 0.0

    def calculate_volume_score(self, payload: GraphPayload | Dict) -> float:
        if isinstance(payload, dict) and "error" in payload:
            return 0.0
        total_items = len(payload.nodes) + len(payload.edges)
        base_score = math.log(total_items + 1) / math.log(101)
        return min(1.0, base_score)

    def calculate_responsiveness_score(self, response_time: float) -> float:
        response_time = min(response_time, Constants.MAX_RESPONSE_TIME)
        return 1.0 - (response_time / Constants.MAX_RESPONSE_TIME)

    def calculate_score(
        self,
        uid: int,
        coldkey: str,
        hotkey: str,
        payload: GraphPayload | ErrorPayload,
        response_time: float,
        batch_id: UUID
    ) -> MinerScore:

        if isinstance(payload, ErrorPayload):
            bt.logging.warning(f"Error received as output from validation process, adding details to miner {uid} records.")
            return MinerScore(
                id=uuid.uuid4(),
                batch_id=batch_id,
                created_at=datetime.now(UTC),
                uid=uid,
                coldkey=coldkey,
                hotkey=hotkey,
                overall_score=0.0,
                volume_score=0.0,
                volume=0,
                responsiveness_score=0.0,
                response_time_seconds=response_time,
                novelty_score=None,
                validation_passed=False,
                error_message=payload.message
            )

        volume = len(payload.nodes) + len(payload.edges)
        volume_score = self.calculate_volume_score(payload)
        responsiveness_score = self.calculate_responsiveness_score(response_time)

        overall_score = sum([
            volume_score * self.importance["volume"],
            responsiveness_score * self.importance["responsiveness"]
        ])

        bt.logging.info(f"Scoring completed for miner {uid}, with overall score: {overall_score}")

        return MinerScore(
            id=uuid.uuid4(),
            batch_id=batch_id,
            created_at=datetime.now(UTC),
            uid=uid,
            coldkey=coldkey,
            hotkey=hotkey,
            overall_score=overall_score,
            volume_score=volume_score,
            volume=volume,
            responsiveness_score=responsiveness_score,
            response_time_seconds=response_time,
            novelty_score=None,
            validation_passed=True,
            error_message=None
        )

def normalize_scores(scores: Dict[int, float]) -> dict[float]:
    """
        Normalize a dictionary of miner Coverage scores to ensure fair comparison.
        Returns list of Coverage scores normalized between 0-1.
    """
    if not scores:
        return {}
    
    min_score = min(scores.values())
    max_score = max(scores.values())
    
    if min_score == max_score:
        return [1.0] * len(scores)
    
    return {uid: round((score - min_score) / (max_score - min_score), 6) for uid, score in scores.items()}
