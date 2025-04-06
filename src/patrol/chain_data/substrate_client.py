import asyncio
import logging
from typing import Any, List
from async_substrate_interface import AsyncSubstrateInterface

# Define the initial block numbers for each group.
GROUP_INIT_BLOCK = {
    1: 3784340,
    2: 4264340,
    3: 4920350,
    4: 5163656,
    5: 5228683,
    6: 5228685,
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        substrate = AsyncSubstrateInterface(url=self.network_url)
        init_block = self.groups[group]
        init_hash = await substrate.get_block_hash(init_block)
        await substrate.init_runtime(block_hash=init_hash)
        return substrate

    async def initialize_connections(self):
        """
        Initializes substrate connections for all groups and starts the keepalive tasks.
        """
        for group in self.groups:
            logger.info(f"Initializing substrate connection for group {group} at block {self.groups[group]}")
            substrate = await self._create_connection(group)
            self.connections[group] = substrate
            # Start a background task for keepalive pings.
            asyncio.create_task(self._keepalive_task(group, substrate))

    async def _reinitialize_connection(self, group: int) -> AsyncSubstrateInterface:
        """
        Reinitializes the substrate connection for a specific group.
        """
        substrate = await self._create_connection(group)
        logger.info(f"Reinitialized connection for group {group}")
        return substrate

    async def _keepalive_task(self, group, substrate):
        """Periodically sends a lightweight ping to keep the connection alive."""
        while True:
            try:
                logger.debug(f"Performing keep alive ping for group {group}")
                await substrate.get_block(block_number=self.groups[group])
                logger.debug(f"Keep alive ping successful for group {group}")
            except Exception as e:
                logger.warning(f"Keepalive failed for group {group}: {e}. Reinitializing connection.")
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
        
        # Retrieve the connection; if missing, reinitialize it.
        substrate = self.connections.get(group)
        if substrate is None:
            logger.info(f"No active connection for group {group}. Reinitializing connection.")
            substrate = await self._reinitialize_connection(group)
            self.connections[group] = substrate

        errors = []
        # First set of retry attempts using the current connection.
        for attempt in range(self.max_retries):
            try:
                query_func = getattr(substrate, method_name)
                return await query_func(*args, **kwargs)
            except Exception as e:
                errors.append(e)
                logger.warning(f"Query error on group {group} attempt {attempt + 1}: {e}")
                if "429" in str(e):
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await asyncio.sleep(0.25)
                
                if attempt == self.max_retries - 1:
                    logger.info(f"Initial query attempts failed for group {group}. Attempting to reinitialize connection.")
                    substrate = await self._reinitialize_connection(group)
                    self.connections[group] = substrate

        # Retry with the reinitialized connection.
        for attempt in range(self.max_retries):
            try:
                query_func = getattr(substrate, method_name)
                return await query_func(*args, **kwargs)
            except Exception as e:
                errors.append(e)
                logger.warning(f"Query error on reinitialized connection for group {group} attempt {attempt + 1}: {e}")
                if "429" in str(e):
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await asyncio.sleep(1)
        
        raise Exception(f"Query failed for group {group} after reinitialization attempts. Errors: {errors}")

    def get_connection(self, group: int) -> AsyncSubstrateInterface:
        """Return the substrate connection for a given group."""
        return self.connections.get(group)
    
    def build_payloads(self, group: int, block_hashes: List[str], preprocessed_lst: List[Any]) -> List[Any]:
        """
        Build payloads using the substrate connection for the given group.
        
        Args:
            group: Group id to retrieve the connection.
            block_hashes: List of block hashes.
            preprocessed_lst: List of preprocessed responses corresponding to the block hashes.
        
        Returns:
            A list of payloads built using the connection's make_payload method.
        """
        substrate = self.get_connection(group)
        return [
            substrate.make_payload(
                str(block_hash),
                preprocessed.method,
                [preprocessed.params[0], block_hash]
            )
            for block_hash, preprocessed in zip(block_hashes, preprocessed_lst)
        ]


async def main():
    
    # Replace with your actual substrate node WebSocket URL.
    network_url = "wss://archive.chain.opentensor.ai:443/"
    
    # Create an instance of SubstrateClient with a shorter keepalive interval.
    client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=5, max_retries=3)
    
    # Initialize substrate connections for all groups.
    await client.initialize_connections()

    block_hash = await client.query(1, "get_block_hash", 3784340)

    logger.info(block_hash)
    
    # Keep the main loop running to observe repeated keepalive pings.
    await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())