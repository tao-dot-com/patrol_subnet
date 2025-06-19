from patrol.validation import TaskType
from patrol.validation.scoring import MinerScoreRepository, MinerScore
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy.orm import mapped_column, Mapped, MappedAsDataclass
from sqlalchemy import DateTime, select, func
from datetime import datetime, UTC
from patrol.validation.persistence import Base
import uuid
from typing import Optional, Iterable


class _MinerScore(Base, MappedAsDataclass):
    __tablename__ = "miner_score"

    id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uid: Mapped[int]
    coldkey: Mapped[str]
    hotkey: Mapped[str]
    overall_score: Mapped[float]
    overall_score_moving_average: Mapped[float]
    volume: Mapped[int]
    volume_score: Mapped[float]
    responsiveness_score: Mapped[float]
    response_time_seconds: Mapped[float]
    novelty_score: Mapped[Optional[float]]
    validation_passed: Mapped[bool]
    error_message: Mapped[Optional[str]]
    task_type: Mapped[Optional[str]]
    accuracy_score: Mapped[Optional[float]]
    scoring_batch: Mapped[Optional[int]]
    stake_removal_score: Mapped[Optional[float]]
    stake_addition_score: Mapped[Optional[float]]

    @classmethod
    def from_miner_score(cls, miner_score: MinerScore):
        return cls(
            id=str(miner_score.id),
            batch_id=str(miner_score.batch_id),
            created_at=miner_score.created_at,
            uid=miner_score.uid,
            coldkey=miner_score.coldkey,
            hotkey=miner_score.hotkey,
            overall_score_moving_average=miner_score.overall_score_moving_average,
            overall_score=miner_score.overall_score,
            volume=miner_score.volume,
            volume_score=miner_score.volume_score,
            responsiveness_score=miner_score.responsiveness_score,
            response_time_seconds=miner_score.response_time_seconds,
            novelty_score=miner_score.novelty_score,
            validation_passed=miner_score.validation_passed,
            error_message=miner_score.error_message,
            task_type=str(miner_score.task_type.value),
            accuracy_score=miner_score.accuracy_score,
            scoring_batch=miner_score.scoring_batch,
            stake_removal_score=miner_score.stake_removal_score,
            stake_addition_score=miner_score.stake_addition_score
        )

    @staticmethod
    def _to_utc(instant):
        """
        SQLite does not persist timezone info, so just set the timezone to UTC if the DB did not give us one.
        """
        return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)

    @property
    def as_score(self) -> MinerScore:
        return MinerScore(
            id=uuid.UUID(self.id),
            batch_id=uuid.UUID(self.batch_id),
            created_at=self._to_utc(self.created_at),
            uid=self.uid,
            coldkey=self.coldkey,
            hotkey=self.hotkey,
            overall_score_moving_average=self.overall_score_moving_average,
            overall_score=self.overall_score,
            volume=self.volume,
            volume_score=self.volume_score,
            responsiveness_score=self.responsiveness_score,
            response_time_seconds=self.response_time_seconds,
            novelty_score=self.novelty_score,
            validation_passed=self.validation_passed,
            error_message=self.error_message,
            task_type=TaskType[self.task_type] if self.task_type else TaskType.COLDKEY_SEARCH,
            accuracy_score=self.accuracy_score,
            scoring_batch=self.scoring_batch,
            stake_removal_score=self.stake_removal_score,
            stake_addition_score=self.stake_addition_score
        )


class DatabaseMinerScoreRepository(MinerScoreRepository):

    def __init__(self, engine: AsyncEngine):
        self.LocalAsyncSession = async_sessionmaker(bind=engine)

    async def add(self, score: MinerScore, session: AsyncSession = None):

        def do_add(sess):
            obj = _MinerScore.from_miner_score(score)
            sess.add(obj)

        if session is None:
            async with self.LocalAsyncSession() as session:
                do_add(session)
                await session.commit()
        else:
            do_add(session)


    async def find_latest_overall_scores(self, miner: tuple[str, int], task_type: TaskType, batch_count: int = 19) -> Iterable[float]:
        async with self.LocalAsyncSession() as session:
            query = select(_MinerScore.overall_score).filter(
                _MinerScore.hotkey == miner[0],
                _MinerScore.uid == miner[1],
                _MinerScore.task_type == task_type.name
            ).order_by(_MinerScore.created_at.desc()).limit(batch_count)
            result = await session.scalars(query)
            return result.all()

    async def find_last_average_overall_scores(self, task_type: TaskType) -> dict[tuple[str, int], float]:

        async with self.LocalAsyncSession() as session:

            ranked = select(
                _MinerScore.overall_score_moving_average,
                _MinerScore.hotkey,
                _MinerScore.uid,
                func.row_number().over(partition_by=[_MinerScore.hotkey, _MinerScore.uid], order_by=_MinerScore.created_at.desc()).label("rnk")
            ).where(_MinerScore.task_type == task_type.name).subquery()

            results = await session.execute(select(ranked).filter(ranked.c.rnk == 1))
            scores = results.mappings().all()
            return {(it['hotkey'], it['uid']): it['overall_score_moving_average'] for it in scores}


    async def find_latest_stake_prediction_overall_scores(self) -> dict[tuple[str, int], float]:
        async with self.LocalAsyncSession() as session:
            # Find latest scoring batch
            latest_batch_query = select(func.max(_MinerScore.scoring_batch))
            latest_scoring_batch = await session.scalar(latest_batch_query)

            aggregate_scores = select(
                _MinerScore.hotkey,
                _MinerScore.uid,
                func.sum(_MinerScore.overall_score).label("aggregate_score")
            ).filter(
                _MinerScore.task_type == TaskType.PREDICT_ALPHA_SELL.name,
                _MinerScore.scoring_batch == latest_scoring_batch
            ).group_by(
                _MinerScore.hotkey,
                _MinerScore.uid,
            )

            results = await session.execute(aggregate_scores)
            scores = results.mappings().all()
            return {(it['hotkey'], it['uid']): it['aggregate_score'] for it in scores}