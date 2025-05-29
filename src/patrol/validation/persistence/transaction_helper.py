
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

class TransactionHelper:
    def __init__(self, engine: AsyncEngine):
        self.LocalSession = async_sessionmaker(bind=engine)

    async def do_in_transaction(self, func):
        async with self.LocalSession() as session:
            async with session.begin():
                return await func(session)

