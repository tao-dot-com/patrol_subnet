from patrol.validation.scoring import MinerScoreRepository, MinerScore
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
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
            error_message=miner_score.error_message
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
            error_message=self.error_message
        )


class DatabaseMinerScoreRepository(MinerScoreRepository):

    def __init__(self, engine: AsyncEngine):
        self.LocalAsyncSession = async_sessionmaker(bind=engine)

    async def add(self, score: MinerScore):
        async with self.LocalAsyncSession() as session:
            obj = _MinerScore.from_miner_score(score)
            session.add(obj)
            await session.commit()

    async def find_latest_overall_scores(self, miner: tuple[str, int], batch_count: int = 19) -> Iterable[float]:
        async with self.LocalAsyncSession() as session:
            query = select(_MinerScore.overall_score).filter(
                _MinerScore.hotkey == miner[0],
                _MinerScore.uid == miner[1],
            ).order_by(_MinerScore.created_at.desc()).limit(batch_count)
            result = await session.scalars(query)
            return result.all()

    async def find_last_average_overall_scores(self) -> dict[tuple[str, int], float]:

        async with self.LocalAsyncSession() as session:

            ranked = select(
                _MinerScore.overall_score_moving_average,
                _MinerScore.hotkey,
                _MinerScore.uid,
                func.row_number().over(partition_by=[_MinerScore.hotkey, _MinerScore.uid], order_by=_MinerScore.created_at.desc()).label("rnk")
            ).subquery()

            results = await session.execute(select(ranked).filter(ranked.c.rnk == 1))
            foo = results.mappings().all()
            return {(r['hotkey'], r['uid']): r['overall_score_moving_average']for r in foo}
