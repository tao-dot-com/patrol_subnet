import asyncio
import bittensor as bt

from async_substrate_interface import AsyncSubstrateInterface
from bittensor import Config

# Define the initial block numbers for each group.
GROUP_INIT_BLOCK = {
    1: 3784340,
    2: 4264340,
    3: 4920350,
    4: 5163656,
    5: 5228683,
    6: 5228685,
}

class SubstrateClient:
    def __init__(self, groups: dict, network_url: str, keepalive_interval: int = 20, max_retries: int = 3):
        """
        Args:
            groups: A dict mapping group_id to initial block numbers.
            network_url: The URL for the archive node.
            keepalive_interval: Interval for keepalive pings in seconds.
            max_retries: Number of times to retry a query before reinitializing the connection.
        """
        self.groups = groups
        self.keepalive_interval = keepalive_interval
        self.max_retries = max_retries
        self.connections = {}  # group_id -> AsyncSubstrateInterface
        self.network_url = network_url

    async def _create_connection(self, group: int) -> AsyncSubstrateInterface:
        """
        Creates and initializes a substrate connection for a given group.
        """
        init_block = self.groups[group]

        # from bittensor.core.async_subtensor import AsyncSubtensor
        # subtensor = AsyncSubtensor(self.network_url)
        # await subtensor.initialize()
        #
        # init_block_hash = await subtensor.get_block_hash(block=init_block)
        # substrate = subtensor.substrate
        # await substrate.init_runtime(block_hash=init_block_hash)
        # return substrate


        substrate = AsyncSubstrateInterface(url=self.network_url)
        init_hash = await substrate.get_block_hash(init_block)
        await substrate.init_runtime(block_hash=init_hash)
        return substrate

    async def initialize_connections(self):
        """
        Initializes substrate connections for all groups and starts the keepalive tasks.
        """
        for group in self.groups:
            bt.logging.info(f"Initializing substrate connection for group {group} at block {self.groups[group]}")
            substrate = await self._create_connection(group)
            self.connections[group] = substrate
            # Start a background task for keepalive pings.
            asyncio.create_task(self._keepalive_task(group, substrate))

    async def _reinitialize_connection(self, group: int) -> AsyncSubstrateInterface:
        """
        Reinitializes the substrate connection for a specific group.
        """
        substrate = await self._create_connection(group)
        bt.logging.info(f"Reinitialized connection for group {group}")
        return substrate

    async def _keepalive_task(self, group, substrate):
        """Periodically sends a lightweight ping to keep the connection alive."""
        while True:
            try:
                bt.logging.debug(f"Performing keep alive ping for group {group}")
                await substrate.get_block(block_number=self.groups[group])
                bt.logging.debug(f"Keep alive ping successful for group {group}")
            except Exception as e:
                bt.logging.warning(f"Keepalive failed for group {group}: {e}. Reinitializing connection.")
                substrate = await self._reinitialize_connection(group)
                self.connections[group] = substrate
            await asyncio.sleep(self.keepalive_interval)

    async def query(self, group: int, method_name: str, *args, **kwargs):
        """
        Executes a query using the substrate connection for the given group.
        Checks if the group is valid, and if the connection is missing, reinitializes it.
        Uses a retry mechanism both before and after reinitializing the connection.

        Args:
            group: The group id for the substrate connection.
            method_name: The name of the substrate method to call (e.g., "get_block_hash").
            *args, **kwargs: Arguments for the query method.

        Returns:
            The result of the query method.
        """
        # Check that the provided group is initialized.
        if group not in self.groups:
            raise Exception(f"Group {group} is not initialized. Available groups: {list(self.groups.keys())}")
        

        errors = []
        # First set of retry attempts using the current connection.
        for attempt in range(self.max_retries):
            try:
                substrate = await self.get_connection(group)

                query_func = getattr(substrate, method_name)
                return await query_func(*args, **kwargs)
            except Exception as e:
                errors.append(e)
                bt.logging.warning(f"Query error on group {group} attempt {attempt + 1}: {e}")
                if "429" in str(e):
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await asyncio.sleep(0.25)
                
                if attempt == self.max_retries - 2:
                    bt.logging.info(f"Initial query attempts failed for group {group}. Attempting to reinitialize connection.")
                    substrate = await self._reinitialize_connection(group)
                    self.connections[group] = substrate
            
        raise Exception(f"Query failed for group {group} after reinitialization attempts. Errors: {errors}")

    async def get_connection(self, group: int) -> AsyncSubstrateInterface:
        """Return the substrate connection for a given group."""
        substrate = self.connections.get(group)
        if substrate is None:
            bt.logging.info(f"No active connection for group {group}. Reinitializing connection.")
            substrate = await self._reinitialize_connection(group)
            self.connections[group] = substrate

        return substrate

if __name__ == "__main__":

    async def example():
    
        # Replace with your actual substrate node WebSocket URL.
        network_url = "wss://archive.chain.opentensor.ai:443/"
        
        # Create an instance of SubstrateClient with a shorter keepalive interval.
        client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=5, max_retries=3)
        
        # Initialize substrate connections for all groups.
        await client.initialize_connections()

        block_hash = await client.query(1, "get_block_hash", 3784340)

        bt.logging.info(block_hash)
        
        # Keep the main loop running to observe repeated keepalive pings.
        await asyncio.sleep(30)
    
    asyncio.run(example())