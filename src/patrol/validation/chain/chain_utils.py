from async_substrate_interface import AsyncSubstrateInterface


class ChainUtils:
    def __init__(self, substrate: AsyncSubstrateInterface):
        self.substrate = substrate

    async def get_current_block(self):
        block = await self.substrate.get_block()
        return block["header"]["number"]
