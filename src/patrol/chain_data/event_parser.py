import json
import time
from typing import List, Dict
import bittensor as bt
import asyncio

from bittensor.core.chain_data.utils import decode_account_id

from patrol.chain_data.coldkey_finder import ColdkeyFinder

def format_address(addr: List) -> str:
    """
    Uses Bittensor's decode_account_id to format the given address.
    Assumes 'addr' is provided in the appropriate format that decode_account_id expects.
    """
    try:
        return decode_account_id(addr[0])
    except Exception as e:
        bt.logging.warning(f"Error Parsing Address from {addr}")
        return addr[0]

def process_balance_events(event: Dict, block_number: int, chain_operations: Dict) -> List[Dict]:
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
                        "coldkey_source": format_address(details.get("from")),
                        "coldkey_destination": format_address(details.get("to")),
                        "category": "balance",
                        "type": "transfer",
                        "evidence": {
                            "rao_amount": details.get("amount"),
                            "block_number": block_number
                        }
                    })
                elif event_type == "Withdraw":
                    chain_operations["withdrawal"].append({
                        "coldkey_source": format_address(details.get("who")),
                        "rao_amount": details.get("amount")
                    })
                elif event_type == "Deposit":
                    chain_operations["deposit"].append({
                        "coldkey_destination": format_address(details.get("who")),
                        "rao_amount": details.get("amount")
                    })
    return formatted

async def process_staking_events(event: Dict, block_number: int, coldkey_finder: ColdkeyFinder) -> List[Dict]:
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
                        delegate_hotkey = format_address(details[0])
                        old_format.append({
                            "coldkey_source": None,
                            "coldkey_destination": await coldkey_finder.find(delegate_hotkey),
                            "category": "staking",
                            "type": "add",
                            "evidence": {
                                "rao_amount": details[1],
                                "delegate_hotkey_destination": delegate_hotkey,
                                "block_number": block_number
                            }
                        })
                    elif len(details) >= 5:
                        delegate_hotkey = format_address(details[1])
                        new_format.append({
                            "coldkey_source": format_address(details[0]),
                            "coldkey_destination": await coldkey_finder.find(delegate_hotkey),
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
                        delegate_hotkey = format_address(details[0])
                        old_format.append({
                            "coldkey_destination": None,
                            "coldkey_source": await coldkey_finder.find(delegate_hotkey),
                            "category": "staking",
                            "type": "remove",
                            "evidence": {
                                "rao_amount": details[1],
                                "delegate_hotkey_source": delegate_hotkey,
                                "block_number": block_number
                            }
                        })
                    elif len(details) >= 5:
                        delegate_hotkey = format_address(details[1])
                        new_format.append({
                            "coldkey_destination": format_address(details[0]),
                            "coldkey_source": await coldkey_finder.find(delegate_hotkey),
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
                    source_delegate_hotkey = format_address(details[1])
                    destination_delegate_hotkey = format_address(details[3])
                    new_format.append({
                        "coldkey_owner": format_address(details[0]),
                        "coldkey_source": await coldkey_finder.find(source_delegate_hotkey),
                        "coldkey_destination": await coldkey_finder.find(destination_delegate_hotkey),
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

def match_old_stake_events(old_stake_events: List[Dict], chain_operations: Dict) -> List[Dict]:
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

async def parse_events(events: List[Dict], block_number: int, coldkey_finder: ColdkeyFinder, semaphore: asyncio.Semaphore) -> List[Dict]:
    formatted = []
    old_stake_format = []
    chain_operations = {"withdrawal": [], "deposit": []}

    for event in events:
        try:
            # Process balances and update chain_operations
            formatted.extend(process_balance_events(event, block_number, chain_operations))
            async with semaphore:
                new_stake, old_stake = await process_staking_events(event, block_number, coldkey_finder)
            formatted.extend(new_stake)
            old_stake_format.extend(old_stake)
        except Exception as e:
            bt.logging.error(f"Error processing event in block {block_number}: {e}")
            continue

    try:
        # Match old-format staking events with corresponding balance events.
        formatted.extend(match_old_stake_events(old_stake_format, chain_operations))
    except Exception as e:
        bt.logging.error(f"Error matching old stake events in block {block_number}: {e}")

    return formatted

async def process_event_data(event_data: dict, coldkey_finder: ColdkeyFinder) -> List[Dict]:
    if not isinstance(event_data, dict):
        bt.logging.error(f"Expected event_data to be a dict, got: {type(event_data)}")
        return []
    if not event_data:
        bt.logging.error("No event data provided.")
        return []

    bt.logging.debug(f"Parsing event data from {len(event_data)} blocks.")
    start_time = time.time()

    semaphore = asyncio.Semaphore(25)

    tasks = []
    for block_key, block_events in event_data.items():
        try:
            bn = int(block_key)
        except ValueError:
            bt.logging.error(f"Block key {block_key} is not convertible to int. Skipping...")
            continue

        if not isinstance(block_events, (list, tuple)):
            bt.logging.error(f"Block {bn} events are not in a tuple or list. Skipping...")
            continue

        tasks.append(parse_events(block_events, bn, coldkey_finder, semaphore))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_parsed_events = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            bt.logging.error(f"Error parsing block {list(event_data.keys())[i]}: {result}")
        else:
            all_parsed_events.extend(result)

    bt.logging.debug(f"Returning {len(all_parsed_events)} parsed events in {round(time.time() - start_time, 4)} seconds.")
    return all_parsed_events

if __name__ == "__main__":

    from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK

    network_url = "wss://archive.chain.opentensor.ai:443/"

    async def example():

        bt.debug()
        
        file_path = "new_event_data.json"
        with open(file_path, "r") as f:
            data = json.load(f)

            # Create an instance of SubstrateClient.
        client = SubstrateClient(groups=GROUP_INIT_BLOCK, network_url=network_url, keepalive_interval=30, max_retries=3)
        
        # Initialize substrate connections for all groups.
        await client.initialize_connections()

        coldkey_finder = ColdkeyFinder(substrate_client=client)
        
        parsed_events = await process_event_data(data, coldkey_finder)
        bt.logging.info(parsed_events)

        with open("output_dict.json", "w") as f:
            json.dump(parsed_events, f, indent=4)

    asyncio.run(example())
    