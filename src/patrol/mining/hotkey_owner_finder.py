import asyncio

from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import VersionData, get_version_for_block
from patrol.protocol import Node, Edge, GraphPayload, HotkeyOwnershipEvidence
from patrol.constants import Constants

class HotkeyOwnerFinder:

    def __init__(self, substrate_client: SubstrateClient):
        self.substrate_client = substrate_client
        self.runtime_versions = self.substrate_client.return_runtime_versions()

    async def get_current_block(self) -> int:
        result = await self.substrate_client.query("get_block", None)
        return result["header"]["number"]

    async def _get_block_metadata(self, block_number: int, current_block: int):
        """
        Returns (block_number, block_hash, runtime_version_for_that_block)
        """
        version = get_version_for_block(block_number, current_block, self.runtime_versions)
        block_hash = await self.substrate_client.query("get_block_hash", None, block_number)
        return block_number, block_hash, version

    async def get_owner_at(self, hotkey: str, block_number: int, current_block: int = None) -> str:
        """
        Helper to fetch owner at exactly `block_number`.
        """
        if current_block is None:
            current_block = await self.get_current_block()

        _, block_hash, version = await self._get_block_metadata(block_number, current_block)
        return await self.substrate_client.query(
            "query",
            version,
            "SubtensorModule",
            "Owner",
            [hotkey],
            block_hash=block_hash
        )

    async def _find_change_block(
        self,
        hotkey: str,
        low: int,
        high: int,
        owner_low: str,
        current_block: int
    ) -> int:
        """
        Binary‐search in (low, high] to find the *first* block where owner != owner_low.
        Assumes that owner at high != owner_low.
        Returns that block number.
        """
        # If the two are adjacent, high must be the change point
        if low + 1 == high:
            return high

        mid = (low + high) // 2
        owner_mid = await self.get_owner_at(hotkey, mid, current_block)

        if owner_mid == owner_low:
            # change must be in (mid, high]
            return await self._find_change_block(hotkey, mid, high, owner_low, current_block)
        else:
            # change is in (low, mid]
            return await self._find_change_block(hotkey, low, mid, owner_low, current_block)

    async def find_owner_ranges(
        self,
        hotkey: str,
        minimum_block: int = Constants.LOWER_BLOCK_LIMIT,
        max_block: int = None
    ) -> GraphPayload:
        """
        Builds a graph of hotkey ownership changes over time.
        Returns a GraphPayload containing wallet and hotkey nodes,
        and edges capturing ownership-change events with evidence.
        """
        if max_block is None:
            current_block = await self.get_current_block()
        else:
            current_block = max_block
        nodes: list[Node] = []
        edges: list[Edge] = []

        # Initialize search
        start = minimum_block
        owner = await self.get_owner_at(hotkey, start, current_block)
        nodes.append(Node(id=owner, type="wallet", origin="bittensor"))

        # Walk through ownership changes until head
        while start <= current_block:
            # Check if owner at chain head changed
            owner_at_head = await self.get_owner_at(hotkey, current_block, current_block)
            if owner_at_head == owner:
                break

            # Binary search for exact change block
            change_block = await self._find_change_block(
                hotkey,
                low=start,
                high=current_block,
                owner_low=owner,
                current_block=current_block
            )
            # New owner from change point
            new_owner = await self.get_owner_at(hotkey, change_block, current_block)
            # Add the new wallet node if unseen
            nodes.append(Node(id=new_owner, type="wallet", origin="bittensor"))

            # Record an ownership-change edge
            edges.append(
                Edge(
                    coldkey_source=owner,
                    coldkey_destination=new_owner,
                    category="coldkey_swap",
                    type="hotkey_ownership",
                    evidence=HotkeyOwnershipEvidence(effective_block_number=change_block),
                    coldkey_owner=new_owner
                )
            )

            # Advance to next segment
            owner = new_owner
            start = change_block

        return GraphPayload(nodes=nodes, edges=edges)



if __name__ == "__main__":
    import time
    from patrol.chain_data.runtime_groupings import load_versions

    async def example():
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        # only keep the runtime we care about
        keep = {"258"}
        versions = {k: versions[k] for k in keep if k in versions}

        client = SubstrateClient(
            runtime_mappings=versions,
            network_url=network_url,
            max_retries=3
        )
        await client.initialize()

        tracker = HotkeyOwnerFinder(client)

        start_time = time.time()
        owner_graph = await tracker.find_owner_ranges(
            hotkey="5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN",
            minimum_block=Constants.LOWER_BLOCK_LIMIT
        )
        elapsed = time.time() - start_time

        print("Owner change ranges:")
        print(owner_graph)

    asyncio.run(example())