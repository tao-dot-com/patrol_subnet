from async_substrate_interface import AsyncSubstrateInterface

class ColdkeyFinder:
    _cache = {}

    def __init__(self, substrate):
        self.substrate = substrate

    async def find(self, hotkey: str) -> str:
        if hotkey in self._cache:
            return self._cache[hotkey]

        result = await self.substrate.query('SubtensorModule', 'Owner', [hotkey])
        self._cache[hotkey] = result
        return result

if __name__ == "__main__":
    import asyncio
    import time
    from patrol.constants import Constants
    
    hotkey = "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3"

    async def example():

        async with AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS) as substrate:
            finder = ColdkeyFinder(substrate)
        
            start_time = time.time()

            coldkey = await finder.find(hotkey)
            response_time = time.time() - start_time

            print(f"Fetched {coldkey} for the first time in {response_time} seconds.")

            start_time = time.time()

            coldkey = await finder.find(hotkey)

            response_time = time.time() - start_time

            print(f"Fetched {coldkey} for the second time in {response_time} seconds.")

    asyncio.run(example())