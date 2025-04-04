from async_substrate_interface import AsyncSubstrateInterface
from patrol.constants import Constants

class ColdkeyFinder:
    _cache = {}

    def __init__(self, substrate: AsyncSubstrateInterface = None):
        self.substrate = substrate
    
    async def initialise_substrate_connection(self) -> None:

        self.substrate = AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS)

        await self.substrate.initialize()

    async def find(self, hotkey: str) -> str:
        if hotkey in self._cache:
            return self._cache[hotkey]

        result = await self.substrate.query('SubtensorModule', 'Owner', [hotkey])
        self._cache[hotkey] = result
        return result

if __name__ == "__main__":
    import asyncio
    import time
    
    hotkey = "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3"

    async def example():

        finder = ColdkeyFinder()
        await finder.initialise_substrate_connection()
    
        start_time = time.time()

        coldkey = await finder.find(hotkey)
        response_time = time.time() - start_time

        print(f"Fetched {coldkey} for the first time in {response_time} seconds.")

        start_time = time.time()

        coldkey = await finder.find(hotkey)

        response_time = time.time() - start_time

        print(f"Fetched {coldkey} for the second time in {response_time} seconds.")

    asyncio.run(example())