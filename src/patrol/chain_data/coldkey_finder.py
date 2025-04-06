import logging

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
            6,
            "query", 
            "SubtensorModule",
            "Owner",
            [hotkey]
        )
        self._cache[hotkey] = result
        return result
    
if __name__ == "__main__":
    import asyncio
    import time
    from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK
    
    hotkey = "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3"

    async def example():
        # Configure logging to see INFO-level messages.
        logging.basicConfig(level=logging.INFO)
        
        # Replace with your actual substrate node WebSocket URL.
        network_url = "wss://archive.chain.opentensor.ai:443/"
        
        # Create an instance of SubstrateClient.
        client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=30, max_retries=3)
        
        # Initialize substrate connections for all groups.
        await client.initialize_connections()

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