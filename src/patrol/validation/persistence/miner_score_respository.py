from patrol.validation.scoring import MinerScoreRepository, MinerScore
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from sqlalchemy.orm import mapped_column, Mapped, MappedAsDataclass
from sqlalchemy import DateTime
from datetime import datetime
from patrol.validation.persistence import Base
import uuid
from typing import Optional


class _MinerScore(Base, MappedAsDataclass):
    __tablename__ = "miner_score"

    id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uid: Mapped[int]
    coldkey: Mapped[str]
    hotkey: Mapped[str]
    overall_score: Mapped[float]
    volume: Mapped[int]
    volume_score: Mapped[float]
    responsiveness_score: Mapped[float]
    response_time_seconds: Mapped[float]
    novelty_score: Mapped[Optional[float]]
    validation_passed: Mapped[bool]
    error_msg: Mapped[Optional[str]]

    @classmethod
    def from_miner_score(cls, miner_score: MinerScore):
        return cls(
            id=str(miner_score.id),
            batch_id=str(miner_score.batch_id),
            created_at=miner_score.created_at,
            uid=miner_score.uid,
            coldkey=miner_score.coldkey,
            hotkey=miner_score.hotkey,
            overall_score=miner_score.overall_score,
            volume=miner_score.volume,
            volume_score=miner_score.volume_score,
            responsiveness_score=miner_score.responsiveness_score,
            response_time_seconds=miner_score.response_time_seconds,
            novelty_score=miner_score.novelty_score,
            validation_passed=miner_score.validation_passed,
            error_msg=miner_score.error_msg
        )


class DatabaseMinerScoreRepository(MinerScoreRepository):

    def __init__(self, engine: AsyncEngine):
        self.LocalAsyncSession = async_sessionmaker(bind=engine)

    async def add(self, score: MinerScore):
        async with self.LocalAsyncSession() as session:
            obj = _MinerScore.from_miner_score(score)
            session.add(obj)
            await session.commit()
