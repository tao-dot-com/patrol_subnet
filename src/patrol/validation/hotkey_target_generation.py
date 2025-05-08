import asyncio
import random

from bittensor.core.chain_data import DynamicInfo

from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import VersionData, get_version_for_block
from patrol.constants import Constants

class HotkeyTargetGenerator:
    def __init__(self, substrate_client: SubstrateClient, runtime_versions: VersionData):
        self.substrate_client = substrate_client
        self.runtime_versions = runtime_versions

    async def get_current_block(self) -> int:
        result = await self.substrate_client.query("get_block", None)
        return result["header"]["number"]

    async def generate_random_block_numbers(self, num_blocks: int, current_block: int) -> list[int]:
        # start_block = random.randint(Constants.LOWER_BLOCK_LIMIT, current_block - num_blocks * 4 * 600)
        start_block = random.randint(Constants.DTAO_RELEASE_BLOCK, current_block - num_blocks * 4 * 600)
        return [start_block + i * 500 for i in range(num_blocks * 4)]

    async def fetch_subnets_data(self, block, current_block):
        block_hash = await self.substrate_client.query("get_block_hash", None, block)
        ver = get_version_for_block(block, current_block, self.runtime_versions)

        if block > Constants.DTAO_RELEASE_BLOCK:

            raw = await self.substrate_client.query(
                "runtime_call",
                ver,
                "SubnetInfoRuntimeApi",
                "get_all_dynamic_info",
                block_hash=block_hash,
            )
            return DynamicInfo.list_from_dicts(raw.decode())
        else:

            # TODO: Add this in here.

            return None
    
    async def query_metagraph_at_block(self, block_number: int, netuid: int):

        # TODO: Add this in here.

        return None

    async def generate_targets(self, num_targets: int = 5) -> list[str]:
        """
        This function aims to generate target hotkeys from active participants in the ecosystem.
        """

        current_block = await self.get_current_block()
        block_numbers = await self.generate_random_block_numbers(num_targets, current_block)

        target_hotkeys = set()
        subnet_list = []
        
        for block_number in block_numbers:
            subnet_data = await self.fetch_subnets_data(block_number, current_block)
            for subnet in subnet_data:
                target_hotkeys.add(subnet.owner_hotkey)
                subnet_list.append((block_number, subnet.netuid))

        for subnet in subnet_list:
            metagraph = await self.query_metagraph_at_block(block_number=subnet[0], netuid=subnet[1])
            print(metagraph)
            # TODO: Parse our just the hotkeys from the metagraph?

        print(subnet_list)

        return target_hotkeys


if __name__ == "__main__":

    from patrol.chain_data.runtime_groupings import load_versions

    async def example():
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        # only keep the runtime we care about
        versions = {k: versions[k] for k in versions.keys() if int(k) > 233}

        client = SubstrateClient(
            runtime_mappings=versions,
            network_url=network_url,
        )
        await client.initialize()

        selector = HotkeyTargetGenerator(substrate_client=client, runtime_versions=versions)
        hotkey_addresses = await selector.generate_targets(num_targets=5)

        print(f"\nSelected {len(hotkey_addresses)} hotkey addresses.")

    asyncio.run(example())