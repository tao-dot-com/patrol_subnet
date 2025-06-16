import asyncio
import random

from async_substrate_interface import AsyncSubstrateInterface
from bittensor.core.chain_data.utils import decode_account_id

from patrol.validation import Constants


#from patrol.chain_data.substrate_client import SubstrateClient
##rom patrol.chain_data.runtime_groupings import get_version_for_block
#from patrol.constants import Constants

class HotkeyTargetGenerator:
    def __init__(self, substrate: AsyncSubstrateInterface):
        #self.substrate_client = substrate_client
        self.substrate = substrate
        #self.runtime_versions = self.substrate_client.return_runtime_versions()

    @staticmethod
    def format_address(addr) -> str:
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
        #block_hash = await self.substrate_client.query("get_block_hash", None, block)
        block_hash = await self.substrate.get_block_hash(block)
        #ver = get_version_for_block(block, current_block, self.runtime_versions)

        subnets = []

        result = await self.substrate.query_map(
            "SubtensorModule",
            "NetworksAdded",
            params=None,
            block_hash=block_hash
        )
        # result = await self.substrate_client.query(
        #     "query_map",
        #     ver,
        #     "SubtensorModule",
        #     "NetworksAdded",
        #     params=None,
        #     block_hash=block_hash
        # )

        async for netuid, exists in result:
            if exists.value:
                subnets.append((block, netuid))

        subnet_owners = set()
        for _, netuid in subnets:
            owner = await self.substrate.query(
                "SubtensorModule",
                "SubnetOwner",
                [netuid],
                block_hash=block_hash
            )
            # owner = await self.substrate_client.query(
            #     "query",
            #     ver,
            #     "SubtensorModule",
            #     "SubnetOwner",
            #     [netuid],
            #     block_hash=block_hash
            # )

            subnet_owners.add(owner)

        return subnets, subnet_owners
    
    async def query_metagraph_direct(self, block_number: int, netuid: int, current_block: int):
        # Get the block hash for the specific block
        block_hash = await self.substrate.get_block_hash(block_number)
        #block_hash = await self.substrate_client.query("get_block_hash", None, block_number)
        # Get the runtime version for this block
        #ver = get_version_for_block(block_number, current_block, self.runtime_versions)

        # Make the runtime API call
        raw = await self.substrate.runtime_call(
            "NeuronInfoRuntimeApi",
            "get_neurons_lite",
            block_hash=block_hash,
            params=[netuid]

        )
        # raw = await self.substrate_client.query(
        #     "runtime_call",
        #     ver,
        #     "NeuronInfoRuntimeApi",
        #     "get_neurons_lite",
        #     block_hash=block_hash,
        #     params=[netuid]
        # )
        
        return raw.decode()

    async def generate_targets(self, max_block_number: int, num_targets: int = 10) -> list[str]:
        """
        This function aims to generate target hotkeys from active participants in the ecosystem.
        """

        block_numbers = await self.generate_random_block_numbers(2, max_block_number)

        target_hotkeys = set()
        subnet_list = []
        
        # Can you turn the below in tasks with asyncio gather 
        tasks = [self.fetch_subnets_and_owners(block_number, max_block_number) for block_number in block_numbers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [result for result in results if result is not None]
        for subnets, subnet_owners in results:
            target_hotkeys.update(subnet_owners)
            subnet_list.extend(subnets)

        # random choice of subnets from list
        subnet_list = random.sample(subnet_list, 5)

        tasks = [self.query_metagraph_direct(block_number=subnet[0], netuid=subnet[1], current_block=max_block_number) for subnet in subnet_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [result for result in results if result is not None]

        for neurons in results:
            hotkeys = [self.format_address(neuron["hotkey"]) for neuron in neurons]
            target_hotkeys.update(hotkeys)

        target_hotkeys = list(target_hotkeys)
        random.shuffle(target_hotkeys)

        return target_hotkeys[:num_targets]
