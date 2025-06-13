from patrol.validation.predict_alpha_sell import ChainStakeEvent, AlphaSellEventRepository, TransactionType
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine
from patrol.validation.persistence import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, delete
from sqlalchemy import DateTime, select, between, func
from datetime import datetime
from typing import Optional

from patrol_common import WalletIdentifier


class _ChainStakeEvent(Base):
    __tablename__ = "alpha_sell_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    block_number: Mapped[int]
    event_type: Mapped[str]
    coldkey: Mapped[str]
    from_hotkey:  Mapped[Optional[str]]
    to_hotkey:  Mapped[Optional[str]]
    rao_amount:  Mapped[int] = mapped_column(BigInteger)
    from_net_uid:  Mapped[Optional[int]]
    to_net_uid:  Mapped[Optional[int]]
    alpha_amount:  Mapped[Optional[int]] = mapped_column(BigInteger)

    @classmethod
    def from_event(cls, event: ChainStakeEvent):
        return cls(
            created_at= event.created_at,
            block_number=event.block_number,
            event_type=event.event_type.name,
            coldkey=event.coldkey,
            from_hotkey=event.from_hotkey,
            to_hotkey=event.to_hotkey,
            rao_amount=event.rao_amount,
            from_net_uid=event.from_net_uid,
            to_net_uid=event.to_net_uid,
            alpha_amount=event.alpha_amount
        )


class DataBaseAlphaSellEventRepository(AlphaSellEventRepository):
    def __init__(self, engine: AsyncEngine) -> None:
        self.LocalSession = async_sessionmaker(bind=engine)

    async def add(self, events: list[ChainStakeEvent]):
        async with self.LocalSession() as session:
            session.add_all([_ChainStakeEvent.from_event(event) for event in events])
            await session.commit()

    async def find_aggregate_stake_movement_by_wallet(self, subnet_id, lower_block, upper_block, transaction_type: TransactionType) -> dict[WalletIdentifier, int]:

        if transaction_type == TransactionType.STAKE_REMOVED:
            selects = [
                _ChainStakeEvent.coldkey,
                _ChainStakeEvent.from_hotkey,
                func.sum(_ChainStakeEvent.rao_amount).label("rao_amount"),
            ]
            group_by = [_ChainStakeEvent.from_hotkey, _ChainStakeEvent.coldkey]
        else:
            selects = [
                _ChainStakeEvent.coldkey,
                _ChainStakeEvent.to_hotkey,
                func.sum(_ChainStakeEvent.rao_amount).label("rao_amount"),
            ]
            group_by = [_ChainStakeEvent.to_hotkey, _ChainStakeEvent.coldkey]

        async with self.LocalSession() as session:
            query = select(
                *selects
            ).filter(
                _ChainStakeEvent.from_net_uid == subnet_id,
                _ChainStakeEvent.event_type == transaction_type.name,
                _ChainStakeEvent.block_number.between(lower_block, upper_block)
            ).group_by(*group_by)

            results = (await session.execute(query)).all()
            return {WalletIdentifier(row[0], row[1]): int(row[2]) for row in results}

    async def find_most_recent_block_collected(self) -> int:
        async with self.LocalSession() as session:
            query = select(func.max(_ChainStakeEvent.block_number))
            result = await session.execute(query)
            return result.scalar()

    async def delete_events_before_block(self, earliest_block: int):
        async with self.LocalSession() as session:
            query = delete(_ChainStakeEvent).where(_ChainStakeEvent.block_number < earliest_block)
            deleted = await session.execute(query)
            await session.commit()
            return deleted.rowcount
