import asyncio
import logging

import bittensor as bt

from async_substrate_interface import AsyncSubstrateInterface
from async_substrate_interface.async_substrate import Websocket

class CustomAsyncSubstrateInterface(AsyncSubstrateInterface):
    def __init__(self, url=None, ws=None, **kwargs):
        """
        Extends AsyncSubstrateInterface to allow injecting a custom websocket connection.
        
        Args:
            url: the URI of the chain to connect to.
            ws: Optional websocket connection to use. If provided, it overrides the default one.
            **kwargs: any additional keyword arguments for the parent class.
        """
        # Initialize the parent class with all normal parameters.
        super().__init__(url, **kwargs)
        # Override the websocket connection if one is provided.
        self.ws = ws

class SubstrateClient:
    def __init__(self, runtime_mappings: dict, network_url: str, websocket: Websocket = None, keepalive_interval: int = 20, max_retries: int = 3):
        """
        Args:
            runtime_mappings: A dict mapping group_id to runtime versions.
            network_url: The URL for the archive node.
            keepalive_interval: Interval for keepalive pings in seconds.
            max_retries: Number of times to retry a query before reinitializing the connection.
        """
        self.runtime_mappings = runtime_mappings
        self.keepalive_interval = keepalive_interval
        self.max_retries = max_retries
        self.websocket = websocket
        self.substrate_cache = {}  # group_id -> AsyncSubstrateInterface
        self.network_url = network_url

    async def initialize(self):
        """
        Initializes the websocket connection and loads metadata instances fol all runtime versions.
        """
        bt.logging.info("Initializing websocket connection.")
        if self.websocket is None:
            self.websocket = Websocket(
                    self.network_url,
                    options={
                        "max_size": 2**32,
                        "write_limit": 2**16,
                    },
                )
        
        await self.websocket.connect(force=True)

        for version, mapping in self.runtime_mappings.items():
            bt.logging.info(f"Initializing substrate instance for version: {version}.")

            substrate = CustomAsyncSubstrateInterface(ws=self.websocket)

            await substrate.init_runtime(block_hash=mapping["block_hash_min"])

            self.substrate_cache[int(version)] = substrate

        bt.logging.info("Substrate client successfully initialized.")

    async def _reinitialize_connection(self):
        """
        Reinitializes the websocket connection.
        """
        if self.websocket:
            await self.websocket.shutdown()
        
        self.websocket = Websocket(
                self.network_url,
                options={
                    "max_size": 2**32,
                    "write_limit": 2**16,
                },
            )
        
        await self.websocket.connect(force=True)
        bt.logging.info("Reinitialized websocket connection.")

    async def query(self, method_name: str, runtime_version: int = None, *args, **kwargs):
        """
        Executes a query using the substrate instance for the given runtime version.
        Checks if the version is valid, and if the connection is missing, reinitializes it.
        Uses a retry mechanism both before and after reinitializing the connection.

        Args:
            runtime_version: The runtime version for the substrate instance.
            method_name: The name of the substrate method to call (e.g., "get_block_hash").
            *args, **kwargs: Arguments for the query method.

        Returns:
            The result of the query method.
        """
        if runtime_version is None:
            bt.logging.debug("No runtime version provided, setting default.")
            runtime_version = max(self.substrate_cache.keys())

        # Check that the provided group is initialized.
        if runtime_version not in self.substrate_cache:
            raise Exception(f"Runtime version {runtime_version} is not initialized. Available versions: {list(self.substrate_cache.keys())}")

        errors = []
        # First set of retry attempts using the current connection.
        for attempt in range(self.max_retries):
            try:
                substrate = self.substrate_cache[runtime_version]

                query_func = getattr(substrate, method_name)
                return await query_func(*args, **kwargs)
            except Exception as e:
                errors.append(e)
                bt.logging.warning(f"Query error on version {runtime_version} attempt {attempt + 1}: {e}")
                if "429" in str(e):
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    await asyncio.sleep(0.25)

                    if attempt == self.max_retries - 2:
                        await self._reinitialize_connection()
            
        raise Exception(f"Query failed for version {runtime_version} after reinitialization attempts. Errors: {errors}")
    
    def return_runtime_versions(self):
        return self.runtime_mappings

if __name__ == "__main__":

    from patrol.chain_data.runtime_groupings import load_versions, get_version_for_block

    async def example():
    
        # Replace with your actual substrate node WebSocket URL.
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()

        # shortening the version dict for dev

        keys_to_keep = {"149", "150", "151"}
        versions = {k: versions[k] for k in keys_to_keep if k in versions}
        
        # Create an instance of SubstrateClient with a shorter keepalive interval.
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        
        # Initialize substrate connections for all groups.
        await client.initialize()

        version = get_version_for_block(3157275, 5400000, versions)
        version = None
        block_hash = await client.query("get_block_hash", version, 3157275)

        await client.websocket.shutdown()

        block_hash = await client.query("get_block_hash", version, 3157275)
        bt.logging.info(block_hash)
    
    asyncio.run(example())