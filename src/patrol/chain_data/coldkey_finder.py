import logging

logger = logging.getLogger(__name__)

class ColdkeyFinder:
    _cache = {}

    def __init__(self, substrate_client):
        """
        Args:
            substrate_client: An instance of SubstrateClient that manages substrate connections.
        """
        self.substrate_client = substrate_client

    async def find(self, hotkey: str) -> str:
        """
        Finds and returns the coldkey owner for the given hotkey.
        Uses the group 6 connection.
        """
        if hotkey in self._cache:
            return self._cache[hotkey]
        
        result = await self.substrate_client.query(
            "query",
            None,
            "SubtensorModule",
            "Owner",
            [hotkey]
        )
        self._cache[hotkey] = result
        return result
    
if __name__ == "__main__":
    import asyncio
    import time
    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions
    
    hotkey = "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3"

    async def example():
        
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        
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