import asyncio

from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import VersionData, get_version_for_block
from patrol.constants import Constants

class HotkeyOwnerFinder:

    def __init__(self, substrate_client: SubstrateClient, runtime_versions: VersionData):
        self.substrate_client = substrate_client
        self.runtime_versions = runtime_versions

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

    async def find_owner_ranges(self, hotkey: str, minimum_block: int = Constants.LOWER_BLOCK_LIMIT):
        """
        Returns a list of dicts
          { "owner": <address>, "ownership_block_start": <start> }
        covering the entire span [minimum_block .. current_block],
        split at *exact* change‐points.
        """
        current_block = await self.get_current_block()
        ranges = []

        # get owner at the very start
        start = minimum_block
        owner = await self.get_owner_at(hotkey, start, current_block)

        # loop until we exhaust up to the head
        while start <= current_block:
            # check owner at the top
            owner_at_head = await self.get_owner_at(hotkey, current_block, current_block)
            if owner_at_head == owner:
                # no more changes—one final range
                ranges.append({
                    "owner": owner,
                    "ownership_block_start": start,
                })
                break

            # there *is* a change somewhere between start and current_block
            change_block = await self._find_change_block(
                hotkey,
                low=start,
                high=current_block,
                owner_low=owner,
                current_block=current_block
            )
            # up to change_block - 1 is still `owner`
            ranges.append({
                "owner": owner,
                "ownership_block_start": start,
            })

            # next segment begins at the change itself
            start = change_block
            owner = await self.get_owner_at(hotkey, start, current_block)

        return ranges


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

        tracker = HotkeyOwnerFinder(client, versions)

        start_time = time.time()
        owner_ranges = await tracker.find_owner_ranges(
            hotkey="5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN",
            minimum_block=Constants.LOWER_BLOCK_LIMIT
        )
        elapsed = time.time() - start_time

        print("Owner change ranges:")
        for r in owner_ranges:
            print(f"  {r['owner']}  start block: {r['ownership_block_start']}")
        print(f"\nFetched in {elapsed:.2f}s")

        print(owner_ranges)

    asyncio.run(example())