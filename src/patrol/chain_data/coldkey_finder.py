import logging
from async_lru import alru_cache

logger = logging.getLogger(__name__)


class ColdkeyFinder:
    def __init__(self, substrate_client):
        self.substrate_client = substrate_client
        self._cached_lookup = self._create_cached_lookup()

    def _create_cached_lookup(self):

        @alru_cache(maxsize=2000)
        async def lookup(hotkey: str) -> str:
            logger.debug("Cache miss for hotkey: %s", hotkey)
            result = await self.substrate_client.query(
                "query",
                None,
                "SubtensorModule",
                "Owner",
                [hotkey]
            )
            return result
        return lookup

    async def find(self, hotkey: str) -> str:
        return await self._cached_lookup(hotkey)
    
if __name__ == "__main__":
    import asyncio
    import time
    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions
    
    hotkey = "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3"

    async def example():
        
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()

        keep = {"258"}
        versions = {k: versions[k] for k in keep if k in versions}
    
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        await client.initialize()

        finder = ColdkeyFinder(substrate_client=client)

        start_time = time.time()

        coldkey = await finder.find(hotkey)
        response_time = time.time() - start_time

        print(f"Fetched {coldkey} for the first time in {response_time} seconds.")

        start_time = time.time()

        coldkey = await finder.find(hotkey)

        response_time = time.time() - start_time

        print(f"Fetched {coldkey} for the second time in {response_time} seconds.")

    asyncio.run(example())