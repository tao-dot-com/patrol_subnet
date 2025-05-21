from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlalchemy.orm import mapped_column, Mapped, composite, relationship

from patrol.validation.persistence import Base
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, PredictionInterval, AlphaSellChallenge, \
    AlphaSellPrediction


class _AlphaSellChallenge(Base):
    __tablename__ = "alpha_sell_challenge"

    task_id: Mapped[str] = mapped_column(primary_key=True)
    batch_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    subnet_uid: Mapped[int]
    hotkeys_ss58_json: Mapped[list[str]] = mapped_column(type_=JSON)

    prediction_interval: Mapped[PredictionInterval] = composite(
        PredictionInterval,
        mapped_column("prediction_interval_start"), mapped_column("prediction_interval_end")
    )
    predictions: Mapped[list["_AlphaSellPrediction"]] = relationship(back_populates="challenge", cascade="all")
    response_time: Mapped[float]

    @classmethod
    def from_challenge(cls, challenge: AlphaSellChallenge):
        return cls(
            task_id=str(challenge.task_id),
            batch_id=str(challenge.batch_id),
            created_at=challenge.created_at,
            subnet_uid=challenge.subnet_uid,
            hotkeys_ss58_json=challenge.hotkeys_ss58,
            prediction_interval=challenge.prediction_interval,
            predictions=[_AlphaSellPrediction.from_prediction(prediction) for prediction in challenge.predictions],
            response_time=challenge.response_time_seconds,
        )


class _AlphaSellPrediction(Base):
    __tablename__ = "alpha_sell_prediction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey(_AlphaSellChallenge.task_id, ondelete="CASCADE"))
    transaction_type: Mapped[str]
    amount: Mapped[float]
    hotkey: Mapped[str]
    challenge: Mapped[_AlphaSellChallenge] = relationship(back_populates="predictions")

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

    async def add(self, challenge: AlphaSellChallenge):
        async with self.LocalSession() as session:
            session.add(_AlphaSellChallenge.from_challenge(challenge))
            await session.commit()