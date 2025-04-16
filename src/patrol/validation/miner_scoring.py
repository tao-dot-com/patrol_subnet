import logging
from typing import Dict, Any
import math
import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.validation.scoring import MinerScore, MinerScoreRepository, ValidationResult
from patrol.constants import Constants

logger = logging.getLogger(__name__)

class MinerScoring:
    def __init__(self, miner_score_repository: MinerScoreRepository):
        self.importance = {
            'volume': 0.9,
            'responsiveness': 0.1,
        }
        self.miner_score_repository = miner_score_repository

    def calculate_novelty_score(self, payload: Dict[str, Any]) -> float:
        # Placeholder for future implementation
        return 0.0

    def calculate_volume_score(self, total_items: int) -> float:
        # Sigmoid formula
        score = 1 / (1 + math.exp(-Constants.STEEPNESS * (total_items - Constants.INFLECTION_POINT)))
        return score

    def calculate_responsiveness_score(self, response_time: float) -> float:
        return Constants.RESPONSE_TIME_HALF_SCORE / (response_time + Constants.RESPONSE_TIME_HALF_SCORE)

    async def calculate_score(
        self,
        uid: int,
        coldkey: str,
        hotkey: str,
        validation_result: ValidationResult,
        response_time: float,
        batch_id: UUID,
        moving_average_denominator: int = 20
    ) -> MinerScore:

        previous_overall_scores = await self.miner_score_repository.find_latest_overall_scores((hotkey, uid), moving_average_denominator - 1)

        if not validation_result.validated:
            logger.warning(f"Zero score added to records for {uid}, reason: {validation_result.message}.")
            return MinerScore(
                id=uuid.uuid4(),
                batch_id=batch_id,
                created_at=datetime.now(UTC),
                uid=uid,
                coldkey=coldkey,
                hotkey=hotkey,
                overall_score_moving_average=(sum(previous_overall_scores) + 0.0) / moving_average_denominator,
                overall_score=0.0,
                volume_score=0.0,
                volume=validation_result.volume,
                responsiveness_score=0.0,
                response_time_seconds=response_time,
                novelty_score=None,
                validation_passed=False,
                error_message=validation_result.message
            )

        volume_score = self.calculate_volume_score(validation_result.volume)
        responsiveness_score = self.calculate_responsiveness_score(response_time)

        overall_score = sum([
            volume_score * self.importance["volume"],
            responsiveness_score * self.importance["responsiveness"]
        ])

        logger.info(f"Scoring completed for miner {uid}, with overall score: {overall_score}")

        return MinerScore(
            id=uuid.uuid4(),
            batch_id=batch_id,
            created_at=datetime.now(UTC),
            uid=uid,
            coldkey=coldkey,
            hotkey=hotkey,
            overall_score_moving_average=(sum(previous_overall_scores) + overall_score) / moving_average_denominator,
            overall_score=overall_score,
            volume_score=volume_score,
            volume=validation_result.volume,
            responsiveness_score=responsiveness_score,
            response_time_seconds=response_time,
            novelty_score=None,
            validation_passed=True,
            error_message=None
        )

    async def calculate_zero_score(
            self, batch_id, uid, coldkey, hotkey, error_message,
            moving_average_denominator: int = 20
    ):
        previous_overall_scores = await self.miner_score_repository.find_latest_overall_scores(
            (hotkey, uid), moving_average_denominator - 1
        )

        return MinerScore(
            id=uuid.uuid4(),
            batch_id=batch_id,
            created_at=datetime.now(UTC),
            uid=uid,
            coldkey=coldkey,
            hotkey=hotkey,
            overall_score_moving_average=(sum(previous_overall_scores) + 0) / moving_average_denominator,
            overall_score=0,
            volume_score=0,
            volume=0,
            responsiveness_score=0,
            response_time_seconds=0,
            novelty_score=None,
            validation_passed=False,
            error_message=error_message
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
