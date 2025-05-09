import asyncio
import random

from bittensor.core.chain_data.utils import decode_account_id

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
    
    @staticmethod
    def format_address(addr: list) -> str:
        """
        Uses Bittensor's decode_account_id to format the given address.
        Assumes 'addr' is provided in the format expected by decode_account_id.
        """
        try:
            return decode_account_id(addr)
        except Exception as e:
            return addr

    async def generate_random_block_numbers(self, num_blocks: int, current_block: int) -> list[int]:
        # start_block = random.randint(Constants.LOWER_BLOCK_LIMIT, current_block - num_blocks * 4 * 600)
        start_block = random.randint(Constants.DTAO_RELEASE_BLOCK, current_block - num_blocks * 4 * 600)
        return [start_block + i * 500 for i in range(num_blocks * 4)]

    async def fetch_subnets_and_owners(self, block, current_block):
        block_hash = await self.substrate_client.query("get_block_hash", None, block)
        ver = get_version_for_block(block, current_block, self.runtime_versions)

        subnets = []

        result = await self.substrate_client.query(
            "query_map",
            ver,
            "SubtensorModule",
            "NetworksAdded",
            params=None,
            block_hash=block_hash
        )

        async for netuid, exists in result:
            if exists.value:
                subnets.append((block, netuid))

        subnet_owners = set()
        for _, netuid in subnets:
            owner = await self.substrate_client.query(
                "query",
                ver,
                "SubtensorModule",
                "SubnetOwner",
                [netuid],
                block_hash=block_hash
            )
            subnet_owners.add(owner)

        return subnets, subnet_owners
    
    async def query_metagraph_direct(self, block_number: int, netuid: int, current_block: int):
        # Get the block hash for the specific block
        block_hash = await self.substrate_client.query("get_block_hash", None, block_number)
        # Get the runtime version for this block
        ver = get_version_for_block(block_number, current_block, self.runtime_versions)

        # Make the runtime API call
        raw = await self.substrate_client.query(
            "runtime_call",
            ver,
            "NeuronInfoRuntimeApi",
            "get_neurons_lite",
            block_hash=block_hash,
            params=[netuid]
        )
        
        return raw.decode()

    async def generate_targets(self, num_targets: int = 10) -> list[str]:
        """
        This function aims to generate target hotkeys from active participants in the ecosystem.
        """

        current_block = await self.get_current_block()
        block_numbers = await self.generate_random_block_numbers(2, current_block)

        target_hotkeys = set()
        subnet_list = []
        
        # Can you turn the below in tasks with asyncio gather 
        tasks = [self.fetch_subnets_and_owners(block_number, current_block) for block_number in block_numbers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [result for result in results if result is not None]
        for subnets, subnet_owners in results:
            target_hotkeys.update(subnet_owners)
            subnet_list.extend(subnets)

        # random choice of subnets from list
        subnet_list = random.sample(subnet_list, 5)

        tasks = [self.query_metagraph_direct(block_number=subnet[0], netuid=subnet[1], current_block=current_block) for subnet in subnet_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [result for result in results if result is not None]

        for neurons in results:
            hotkeys = [self.format_address(neuron["hotkey"]) for neuron in neurons]
            target_hotkeys.update(hotkeys)

        target_hotkeys = list(target_hotkeys)
        random.shuffle(target_hotkeys)

        return target_hotkeys[:num_targets]

if __name__ == "__main__":
    import time
    from patrol.chain_data.runtime_groupings import load_versions

    async def example():
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        # only keep the runtime we care about
        versions = {k: versions[k] for k in versions.keys() if int(k) == 149}

        # version = get_version_for_block(3014350, 5014352, versions)
        # print(version)

        client = SubstrateClient(
            runtime_mappings=versions,
            network_url=network_url,
        )
        await client.initialize()

        start_time = time.time()

        selector = HotkeyTargetGenerator(substrate_client=client, runtime_versions=versions)
        hotkey_addresses = await selector.generate_targets(num_targets=256)        
        
        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")

        print(f"\nSelected {len(hotkey_addresses)} hotkey addresses.")

    asyncio.run(example())