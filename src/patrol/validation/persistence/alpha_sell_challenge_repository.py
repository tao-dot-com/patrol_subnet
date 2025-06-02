from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import mapped_column, Mapped, composite, relationship, joinedload

from patrol.validation.persistence import Base
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, PredictionInterval, \
    AlphaSellPrediction, AlphaSellChallengeTask, AlphaSellChallengeBatch, TransactionType, AlphaSellChallengeMiner


class _AlphaSellChallengeBatch(Base):
    __tablename__ = "alpha_sell_challenge_batch"

    id: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    subnet_uid: Mapped[int]
    hotkeys_ss58_json: Mapped[list[str]] = mapped_column(type_=JSON)
    prediction_interval_start: Mapped[int] = mapped_column()
    prediction_interval_end: Mapped[int] = mapped_column()
    is_ready_for_scoring: Mapped[bool] = mapped_column(default=False)

    prediction_interval: Mapped[PredictionInterval] = composite(
        PredictionInterval,
        prediction_interval_start, prediction_interval_end
    )

    @classmethod
    def from_batch(cls, batch: AlphaSellChallengeBatch):
        return cls(
            id=str(batch.batch_id),
            created_at=batch.created_at,
            subnet_uid=batch.subnet_uid,
            hotkeys_ss58_json=batch.hotkeys_ss58,
            prediction_interval=batch.prediction_interval,
        )

    @property
    def batch(self) -> AlphaSellChallengeBatch:
        return AlphaSellChallengeBatch(
            UUID(self.id), self.created_at, self.subnet_uid, self.prediction_interval, self.hotkeys_ss58_json,
        )

class _AlphaSellChallengeTask(Base):
    __tablename__ = "alpha_sell_challenge_task"

    id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey(_AlphaSellChallengeBatch.id, ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    miner_hotkey: Mapped[str]
    miner_coldkey: Mapped[str]
    miner_uid: Mapped[int]
    predictions: Mapped[list["_AlphaSellPrediction"]] = relationship(back_populates="task", cascade="all")
    response_time: Mapped[float] = mapped_column(default=0.0)
    is_scored: Mapped[bool] = mapped_column(default=False)
    has_error: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[Optional[str]]

    @classmethod
    def from_task(cls, task: AlphaSellChallengeTask):
        return cls(
            id=str(task.task_id),
            batch_id=str(task.batch_id),
            created_at=task.created_at,
            miner_hotkey=task.miner.hotkey,
            miner_coldkey=task.miner.coldkey,
            miner_uid=task.miner.uid,
            predictions=[] if not task.predictions else [_AlphaSellPrediction.from_prediction(prediction) for prediction in task.predictions],
            has_error=task.has_error,
            error_message=task.error_message,
        )

    @property
    def task(self):
        return AlphaSellChallengeTask(
            batch_id=UUID(self.batch_id),
            task_id=UUID(self.id),
            created_at=self.created_at,
            miner=AlphaSellChallengeMiner(self.miner_hotkey, self.miner_coldkey, self.miner_uid),
            predictions=[it.prediction for it in self.predictions],
            has_error=self.has_error,
            error_message=self.error_message,
        )


class _AlphaSellPrediction(Base):
    __tablename__ = "alpha_sell_prediction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey(_AlphaSellChallengeTask.id, ondelete="CASCADE"))
    transaction_type: Mapped[str]
    amount: Mapped[float]
    hotkey: Mapped[str]
    coldkey: Mapped[str]
    task: Mapped[_AlphaSellChallengeTask] = relationship(back_populates="predictions")

    @classmethod
    def from_prediction(cls, prediction: AlphaSellPrediction):
        return cls(
            amount=prediction.amount,
            hotkey=prediction.wallet_hotkey_ss58,
            coldkey=prediction.wallet_coldkey_ss58,
            transaction_type=prediction.transaction_type.name
        )

    @property
    def prediction(self) -> AlphaSellPrediction:
        return AlphaSellPrediction(
            self.hotkey, self.coldkey, TransactionType[self.transaction_type], self.amount
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
        async with self.LocalSession() as session:
            query = select(_AlphaSellChallengeBatch).filter(
                _AlphaSellChallengeBatch.prediction_interval_end <= upper_block,
                _AlphaSellChallengeBatch.is_ready_for_scoring == True,
            )
            results = await session.scalars(query)
            return [it.batch for it in results]

    async def find_tasks(self, batch_id: UUID) -> list[AlphaSellChallengeTask]:
        async with self.LocalSession() as session:
            query = (select(_AlphaSellChallengeTask)
                     .filter(
                        _AlphaSellChallengeTask.batch_id == str(batch_id),
                        _AlphaSellChallengeTask.is_scored == False
                     )
                     .outerjoin(_AlphaSellChallengeTask.predictions)
                     .options(joinedload(_AlphaSellChallengeTask.predictions))
            )
            results = await session.scalars(query)
            tasks = [it.task for it in results.unique().all()]
            return tasks

    async def find_earliest_prediction_block(self) -> int:
        async with self.LocalSession() as session:
            query = select(func.min(_AlphaSellChallengeBatch.prediction_interval_start))
            result = await session.scalar(query)
            return result

    async def mark_task_scored(self, task_id, session):
        query = (update(_AlphaSellChallengeTask)
            .where(_AlphaSellChallengeTask.id == str(task_id))
            .values(is_scored=True)
         )
        await session.execute(query)

    async def remove_if_fully_scored(self, batch_id: UUID):
        async with self.LocalSession() as session:
            query = select(func.count()).select_from(_AlphaSellChallengeTask).filter(
                _AlphaSellChallengeTask.is_scored == False,
                _AlphaSellChallengeTask.batch_id == str(batch_id)
            )
            unscored_count = await session.scalar(query)

            if unscored_count == 0:
                query = delete(_AlphaSellChallengeBatch).filter(
                    _AlphaSellChallengeBatch.id == str(batch_id),
                    _AlphaSellChallengeBatch.is_ready_for_scoring == True
                )
                await session.execute(query)
                await session.commit()

    async def mark_batches_ready_for_scoring(self, batch_ids: list[UUID]):
        async with self.LocalSession() as session:
            query = (update(_AlphaSellChallengeBatch)
                .where(_AlphaSellChallengeBatch.id.in_([str(b) for b in batch_ids]))
                .values(is_ready_for_scoring=True)
            )

            await session.execute(query)
            await session.commit()

