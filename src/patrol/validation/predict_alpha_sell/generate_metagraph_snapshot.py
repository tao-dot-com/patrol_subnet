import asyncio
import random
import os

from bittensor.core.chain_data.utils import decode_account_id
import json
from datetime import datetime

from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.runtime_groupings import get_version_for_block
from patrol.constants import Constants
from patrol.chain_data.runtime_groupings import load_versions
from patrol.validation.predict_alpha_sell.alpha_sell_constants import VALID_SUBNET_IDS

class SnapshotGenerator:
    def __init__(self, substrate_client: SubstrateClient):
        self.substrate_client = substrate_client
        self.runtime_versions = self.substrate_client.return_runtime_versions()
    
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
    
    async def fetch_subnets(self, block, current_block):
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

        return subnets
    
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
    
    async def generate_miner_hotkeys(self, block_number: int, current_block: int, 
                               num_subnets: int = 5, num_targets: int = 10,
                               valid_subnet_ids: list[int] = None) -> tuple[list[int], list[list[str]]]:
        """
        Generates lists of miner hotkeys organized by subnet.
        
        Args:
            block_number: The block number to query
            current_block: The current block number
            num_subnets: The number of subnets to return data for
            num_targets: The maximum number of hotkeys to return per subnet
            valid_subnet_ids: Optional list of valid subnet IDs to filter by
            
        Returns:
            A tuple containing:
            - subnet_list: List of netuid integers
            - hotkeys_by_subnet: List of hotkey lists, where each list contains the hotkeys for a subnet
        """
        # Fetch subnets (this returns tuples of (block, netuid))
        subnets = await self.fetch_subnets(block_number, current_block)

        print(f"Total subnets found: {len(subnets)}")
        
        # Filter by valid_subnet_ids if provided
        if valid_subnet_ids is not None:
            subnets = [(block, netuid) for block, netuid in subnets if netuid in valid_subnet_ids]
            print(f"Subnets after filtering by valid_subnet_ids: {len(subnets)}")
        
        # Random choice of subnets from list
        if len(subnets) > num_subnets:
            subnets = random.sample(subnets, num_subnets)

        # Query metagraph for each subnet
        tasks = [self.query_metagraph_direct(
            block_number=subnet[0], 
            netuid=subnet[1], 
            current_block=current_block
        ) for subnet in subnets]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = [result for result in results if result is not None]

        # Create a list of hotkey lists, one for each subnet
        hotkeys_by_subnet = []
        
        for neurons in results:
            #Filter out validators by non-zero dividends
            miner_neurons = [neuron for neuron in neurons if neuron['dividends'] == 0]
            subnet_hotkeys = [self.format_address(neuron["hotkey"]) for neuron in miner_neurons]
            
            # Limit to num_targets hotkeys per subnet if specified
            if num_targets > 0 and len(subnet_hotkeys) > num_targets:
                subnet_hotkeys = subnet_hotkeys[:num_targets]
                
            hotkeys_by_subnet.append(subnet_hotkeys)

        # Extract just the netuid values for the return
        subnet_list = [subnet[1] for subnet in subnets]
        
        return subnet_list, hotkeys_by_subnet
        
    
    async def get_alpha_stake_hotkey(self, hotkey: str, netuid, block: int) -> int:
        """
        Get the total stake for a given hotkey at a specific block.
        
        Args:
            hotkey: The SS58 address of the hotkey to check
            netuid: The subnet ID to query
            block: The block number to query
            
        Returns:
            The total stake amount as an integer
        """    
        # Get the block hash for the specific block
        block_hash = await self.substrate_client.query("get_block_hash", None, block)
        
        # Get the runtime version for this block
        ver = get_version_for_block(block, block, self.runtime_versions)
        
        # Query the TotalHotkeyStake storage item for this hotkey
        result = await self.substrate_client.query(
            "query",
            ver,
            "SubtensorModule",
            "TotalHotkeyAlpha",
            [hotkey, netuid],
            block_hash=block_hash
        )
        
        return result

    async def get_alpha_stakes_by_subnet(self, block_number: int, subnet_list: list[int], hotkeys_by_subnet: list[list[str]]) -> dict[int, dict[str, int]]:
        """
        Creates a dictionary mapping subnets to their hotkeys and alpha stake values.
        
        Args:
            block_number: The block number to query
            subnet_list: List of subnet IDs
            hotkeys_by_subnet: List of hotkey lists, where each list contains the hotkeys for a subnet
            
        Returns:
            A dictionary mapping each subnet ID to a nested dictionary of {hotkey: alpha_stake_value}
        """
        # Initialize the result dictionary
        result = {netuid: {} for netuid in subnet_list}
        
        # Create all tasks for querying alpha stakes
        all_tasks = []
        netuid_hotkey_pairs = []
        
        # For each subnet and its corresponding hotkey list
        for i, (netuid, subnet_hotkeys) in enumerate(zip(subnet_list, hotkeys_by_subnet)):
            for hotkey in subnet_hotkeys:
                # Create a task to get the alpha stake for this hotkey in this subnet
                task = self.get_alpha_stake_hotkey(hotkey, netuid, block_number)
                all_tasks.append(task)
                netuid_hotkey_pairs.append((netuid, hotkey))
        
        # Execute all tasks concurrently
        alpha_stakes = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        # Process the results
        for (netuid, hotkey), alpha_stake in zip(netuid_hotkey_pairs, alpha_stakes):
            # Skip any failures
            if isinstance(alpha_stake, Exception):
                continue
                
            # Add the alpha stake value to the result dictionary
            if hasattr(alpha_stake, 'value'):
                result[netuid][hotkey] = alpha_stake.value
            else:
                # Handle case where alpha_stake doesn't have a value attribute
                result[netuid][hotkey] = alpha_stake
        
        return result

if __name__ == "__main__":
    async def example():
        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()

        # shortening the version dict for dev
        keys_to_keep = {"161"}
        versions = {k: versions[k] for k in keys_to_keep if k in versions}
        
        # Create an instance of SubstrateClient
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        
        # Initialize the client if needed
        await client.initialize()
        
        # Create the snapshot generator
        generator = SnapshotGenerator(substrate_client=client)
        
        # Define block range
        max_block = 5500000
        min_block = 4920351  # DTAO release block
        
        # Store all results
        all_results = []
        
        # Run 100 times
        for i in range(100):
            # Generate random block number
            block_number = random.randint(min_block, max_block)
            print(f"\nRun {i+1}/100: Processing block {block_number}")
            
            try:
                # Generate miner hotkeys
                subnets, hotkeys = await generator.generate_miner_hotkeys(
                    block_number, 
                    max_block,  # Using max_block as current_block
                    num_subnets=5, 
                    num_targets=5,
                    valid_subnet_ids=VALID_SUBNET_IDS
                )

                # Get alpha stakes
                alpha_stakes_dict = await generator.get_alpha_stakes_by_subnet(block_number, subnets, hotkeys)
                
                # Store results
                result = {
                    "block_number": block_number,
                    "alpha_stakes": alpha_stakes_dict
                }
                all_results.append(result)
                
                print(f"Successfully processed block {block_number}")
                
            except Exception as e:
                print(f"Error processing block {block_number}: {str(e)}")
                continue
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alpha_data/alpha_stakes_analysis_{timestamp}.json"

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(all_results, f, indent=2)
        
        print(f"\nAnalysis complete. Results saved to {filename}")
        print(f"Successfully processed {len(all_results)} blocks out of 100 attempts")

    asyncio.run(example())
