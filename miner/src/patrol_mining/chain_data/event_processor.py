import logging
import time
from typing import List, Dict, Tuple
import asyncio

from bittensor.core.chain_data.utils import decode_account_id
from patrol_mining.chain_data.coldkey_finder import ColdkeyFinder

logger = logging.getLogger(__name__)

class EventProcessor:
    def __init__(self, coldkey_finder: ColdkeyFinder):
        """
        Args:
            coldkey_finder: An instance of ColdkeyFinder to resolve coldkey owners.
        """
        self.coldkey_finder = coldkey_finder
        self.semaphore = asyncio.Semaphore(25)

    @staticmethod
    def format_address(addr: List) -> str:
        """
        Uses Bittensor's decode_account_id to format the given address.
        Assumes 'addr' is provided in the format expected by decode_account_id.
        """
        try:
            return decode_account_id(addr[0])
        except Exception as e:
            logger.warning(f"Error parsing address from {addr}: {e}")
            return addr[0]

    def process_balance_events(self, event: Dict, block_number: int, chain_operations: Dict) -> List[Dict]:
        """
        Process balance events from a block event.
        """
        formatted = []
        if "event" not in event:
            return formatted

        for module, event_list in event["event"].items():
            if module != "Balances":
                continue
            for item in event_list:
                for event_type, details in item.items():
                    if event_type == "Transfer":
                        formatted.append({
                            "coldkey_source": self.format_address(details.get("from")),
                            "coldkey_destination": self.format_address(details.get("to")),
                            "category": "balance",
                            "type": "transfer",
                            "evidence": {
                                "rao_amount": details.get("amount"),
                                "block_number": block_number
                            }
                        })
                    elif event_type == "Withdraw":
                        chain_operations["withdrawal"].append({
                            "coldkey_source": self.format_address(details.get("who")),
                            "rao_amount": details.get("amount")
                        })
                    elif event_type == "Deposit":
                        chain_operations["deposit"].append({
                            "coldkey_destination": self.format_address(details.get("who")),
                            "rao_amount": details.get("amount")
                        })
        return formatted

    async def process_staking_events(self, event: Dict, block_number: int) -> Tuple[List[Dict], List[Dict]]:
        """
        Process staking events from a block event. Returns two formats:
          - new_format: Detailed staking events.
          - old_format: Events in an older format.
        """
        new_format = []
        old_format = []
        if "event" not in event:
            return new_format, old_format

        for module, event_list in event["event"].items():
            if module != "SubtensorModule":
                continue
            for item in event_list:
                for event_type, details in item.items():
                    if event_type == "StakeAdded":
                        if len(details) == 2:
                            delegate_hotkey = self.format_address(details[0])
                            old_format.append({
                                "coldkey_source": None,
                                "coldkey_destination": await self.coldkey_finder.find(delegate_hotkey),
                                "category": "staking",
                                "type": "add",
                                "evidence": {
                                    "rao_amount": details[1],
                                    "delegate_hotkey_destination": delegate_hotkey,
                                    "block_number": block_number
                                }
                            })
                        elif len(details) >= 5:
                            delegate_hotkey = self.format_address(details[1])
                            new_format.append({
                                "coldkey_source": self.format_address(details[0]),
                                "coldkey_destination": await self.coldkey_finder.find(delegate_hotkey),
                                "category": "staking",
                                "type": "add",
                                "evidence": {
                                    "rao_amount": details[2],
                                    "delegate_hotkey_destination": delegate_hotkey,
                                    "alpha_amount": details[3],
                                    "destination_net_uid": details[4],
                                    "block_number": block_number
                                }
                            })
                    elif event_type == "StakeRemoved":
                        if len(details) == 2:
                            delegate_hotkey = self.format_address(details[0])
                            old_format.append({
                                "coldkey_destination": None,
                                "coldkey_source": await self.coldkey_finder.find(delegate_hotkey),
                                "category": "staking",
                                "type": "remove",
                                "evidence": {
                                    "rao_amount": details[1],
                                    "delegate_hotkey_source": delegate_hotkey,
                                    "block_number": block_number
                                }
                            })
                        elif len(details) >= 5:
                            delegate_hotkey = self.format_address(details[1])
                            new_format.append({
                                "coldkey_destination": self.format_address(details[0]),
                                "coldkey_source": await self.coldkey_finder.find(delegate_hotkey),
                                "category": "staking",
                                "type": "remove",
                                "evidence": {
                                    "rao_amount": details[2],
                                    "delegate_hotkey_source": delegate_hotkey,
                                    "alpha_amount": details[3],
                                    "source_net_uid": details[4],
                                    "block_number": block_number
                                }
                            })
                    elif event_type == "StakeMoved" and len(details) == 6:
                        source_delegate_hotkey = self.format_address(details[1])
                        destination_delegate_hotkey = self.format_address(details[3])
                        new_format.append({
                            "coldkey_owner": self.format_address(details[0]),
                            "coldkey_source": await self.coldkey_finder.find(source_delegate_hotkey),
                            "coldkey_destination": await self.coldkey_finder.find(destination_delegate_hotkey),
                            "category": "staking",
                            "type": "move",
                            "evidence": {
                                "rao_amount": details[5],
                                "delegate_hotkey_source": source_delegate_hotkey,
                                "delegate_hotkey_destination": destination_delegate_hotkey,
                                "source_net_uid": details[2],
                                "destination_net_uid": details[4],
                                "block_number": block_number
                            }
                        })
        return new_format, old_format

    @staticmethod
    def match_old_stake_events(old_stake_events: List[Dict], chain_operations: Dict) -> List[Dict]:
        """
        Matches old-format staking events with corresponding balance events.
        """
        matched = []
        for entry in old_stake_events:
            if entry["type"] == "add":
                matches = [x for x in chain_operations["withdrawal"] 
                           if x["rao_amount"] == entry["evidence"]["rao_amount"]]
                if len(matches) == 1:
                    entry["coldkey_source"] = matches[0]["coldkey_source"]
                    matched.append(entry)
            elif entry["type"] == "remove":
                matches = [x for x in chain_operations["deposit"] 
                           if x["rao_amount"] == entry["evidence"]["rao_amount"]]
                if len(matches) == 1:
                    entry["coldkey_destination"] = matches[0]["coldkey_destination"]
                    matched.append(entry)
        return matched

    async def parse_events(self, events: List[Dict], block_number: int, semaphore: asyncio.Semaphore) -> List[Dict]:
        """
        Parses events for a given block.
        """
        formatted = []
        old_stake_format = []
        chain_operations = {"withdrawal": [], "deposit": []}

        for event in events:
            try:
                # Process balance events and update chain operations.
                formatted.extend(self.process_balance_events(event, block_number, chain_operations))
                async with semaphore:
                    new_stake, old_stake = await self.process_staking_events(event, block_number)
                formatted.extend(new_stake)
                old_stake_format.extend(old_stake)
            except Exception as e:
                logger.exception(f"Error processing event in block {block_number}: {e}")
                continue

        try:
            formatted.extend(self.match_old_stake_events(old_stake_format, chain_operations))
        except Exception as e:
            logger.error(f"Error matching old stake events in block {block_number}: {e}")

        return formatted

    async def process_event_data(self, event_data: dict) -> List[Dict]:
        """
        Processes event data across multiple blocks.
        """
        if not isinstance(event_data, dict):
            logger.error(f"Expected event_data to be a dict, got: {type(event_data)}")
            return []
        if not event_data:
            logger.error("No event data provided.")
            return []

        logger.debug(f"Parsing event data from {len(event_data)} blocks.")
        start_time = time.time()

        tasks = []
        for block_key, block_events in event_data.items():
            try:
                bn = int(block_key)
            except ValueError:
                logger.error(f"Block key {block_key} is not convertible to int. Skipping...")
                continue

            if not isinstance(block_events, (list, tuple)):
                logger.error(f"Block {bn} events are not in a tuple or list. Skipping...")
                continue

            tasks.append(self.parse_events(block_events, bn, self.semaphore))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_parsed_events = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error parsing block {list(event_data.keys())[i]}: {result}")
            else:
                all_parsed_events.extend(result)

        logger.debug(f"Returning {len(all_parsed_events)} parsed events in {round(time.time() - start_time, 4)} seconds.")
        return all_parsed_events
    
if __name__ == "__main__":

    import json
    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions

    network_url = "wss://archive.chain.opentensor.ai:443/"
    versions = load_versions()

    async def example():

        file_path = "raw_event_data.json"  # you will need to create this by running event_fetcher and saving the output.
        with open(file_path, "r") as f:
            data = json.load(f)

        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        await client.initialize()

        coldkey_finder = ColdkeyFinder(substrate_client=client)

        event_processor = EventProcessor(coldkey_finder=coldkey_finder)
        
        parsed_events = await event_processor.process_event_data(data)
        logger.info(parsed_events)

    asyncio.run(example())