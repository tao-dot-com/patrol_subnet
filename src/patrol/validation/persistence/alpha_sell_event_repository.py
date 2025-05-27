from patrol.validation.predict_alpha_sell import ChainStakeEvent, AlphaSellEventRepository, TransactionType
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from patrol.validation.persistence import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from sqlalchemy import DateTime, select, between, func
from datetime import datetime
from typing import Optional

class _ChainStakeEvent(Base):
    __tablename__="alpha_sell_event"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    block_number: Mapped[int]
    event_type: Mapped[str]
    coldkey: Mapped[str]
    hotkey:  Mapped[str]
    rao_amount:  Mapped[int] = mapped_column(BigInteger)
    net_uid:  Mapped[int]
    alpha_amount:  Mapped[Optional[int]] = mapped_column(BigInteger)
    @classmethod
    def from_event(cls, event: ChainStakeEvent):
        return cls(created_at = event.created_at, 
        block_number= event.block_number,
        event_type= event.event_type,
        coldkey= event.coldkey,
        hotkey= event.hotkey,
        rao_amount= event.rao_amount,
        net_uid= event.net_uid,
        alpha_amount= event.alpha_amount)

        

class DataBaseAlphaSellEventRepository(AlphaSellEventRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self.LocalSession = async_sessionmaker(bind=engine)
    async def add(self, events: list[ChainStakeEvent]):
        async with self.LocalSession() as session:
            session.add_all([_ChainStakeEvent.from_event(event) for event in events])
            await session.commit()

    async def find_aggregate_stake_movement_by_hotkey(self, subnet_id, lower_block, upper_block, transaction_type: TransactionType) -> dict[str, int]:
        async with self.LocalSession() as session:
            query = select(
                _ChainStakeEvent.hotkey,
                func.sum(_ChainStakeEvent.rao_amount).label("rao_amount"),
            ).filter(
                _ChainStakeEvent.net_uid == subnet_id,
                _ChainStakeEvent.block_number.between(lower_block, upper_block)
            ).group_by(_ChainStakeEvent.hotkey)
            results = (await session.execute(query)).all()
            results_dict = dict(results)
            return results_dict
