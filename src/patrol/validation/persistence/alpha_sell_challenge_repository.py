from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import mapped_column, Mapped, composite, relationship

from patrol.validation.persistence import Base
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, PredictionInterval, \
    AlphaSellPrediction, AlphaSellChallengeTask, AlphaSellChallengeBatch


class _AlphaSellChallengeBatch(Base):
    __tablename__ = "alpha_sell_challenge_batch"

    id: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    subnet_uid: Mapped[int]
    hotkeys_ss58_json: Mapped[list[str]] = mapped_column(type_=JSON)

    prediction_interval: Mapped[PredictionInterval] = composite(
        PredictionInterval,
        mapped_column("prediction_interval_start"), mapped_column("prediction_interval_end")
    )
    #predictions: Mapped[list["_AlphaSellPrediction"]] = relationship(back_populates="challenge", cascade="all")
    #response_time: Mapped[float]

    @classmethod
    def from_batch(cls, batch: AlphaSellChallengeBatch):
        return cls(
            id=str(batch.batch_id),
            created_at=batch.created_at,
            subnet_uid=batch.subnet_uid,
            hotkeys_ss58_json=batch.hotkeys_ss58,
            prediction_interval=batch.prediction_interval,
        )

class _AlphaSellChallengeTask(Base):
    __tablename__ = "alpha_sell_challenge_task"

    id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey(_AlphaSellChallengeBatch.id, ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    miner_hotkey: Mapped[str]
    miner_uid: Mapped[int]
    predictions: Mapped[list["_AlphaSellPrediction"]] = relationship(back_populates="task", cascade="all")
    response_time: Mapped[float]

    @classmethod
    def from_task(cls, task: AlphaSellChallengeTask):
        return cls(
            id=str(task.task_id),
            batch_id=str(task.batch_id),
            created_at=task.created_at,
            miner_hotkey=task.miner[0],
            miner_uid=task.miner[1],
            predictions=[_AlphaSellPrediction.from_prediction(prediction) for prediction in task.predictions],
            response_time=task.response_time_seconds,
        )


class _AlphaSellPrediction(Base):
    __tablename__ = "alpha_sell_prediction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey(_AlphaSellChallengeTask.id, ondelete="CASCADE"))
    transaction_type: Mapped[str]
    amount: Mapped[float]
    hotkey: Mapped[str]
    task: Mapped[_AlphaSellChallengeTask] = relationship(back_populates="predictions")

    @classmethod
    def from_prediction(cls, prediction: AlphaSellPrediction):
        return cls(
            amount=prediction.amount,
            hotkey=prediction.wallet_hotkey_ss58,
            transaction_type=prediction.transaction_type.name
        )


class DatabaseAlphaSellChallengeRepository(AlphaSellChallengeRepository):
    def __init__(self, async_engine: AsyncEngine):
        self.LocalSession = async_sessionmaker(bind=async_engine)

    async def add(self, batch: AlphaSellChallengeBatch):
        async with self.LocalSession() as session:
            session.add(_AlphaSellChallengeBatch.from_batch(batch))
            await session.commit()

    async def add_task(self, task):
        async with self.LocalSession() as session:
            session.add(_AlphaSellChallengeTask.from_task(task))
            await session.commit()

    async def find_scorable_challenges(self, upper_block: int) -> list[AlphaSellChallengeBatch]:
        pass

