import asyncio
import pytest
from patrol.chain_data.event_processor import EventProcessor
import bittensor as bt

# A dummy implementation for ColdkeyFinder for testing purposes.
class DummyColdkeyFinder:
    async def find(self, delegate_hotkey: str) -> str:
        # Simply return a value based on the delegate hotkey.
        return "owner_" + delegate_hotkey

# Dummy decode_account_id functions to patch the real one.
def dummy_decode_account_id(value):
    return "decoded_" + value

def dummy_decode_account_id_error(value):
    raise Exception("Decode error")

# -----------------------
# Tests for format_address
# -----------------------

def test_format_address_success(monkeypatch):
    # Patch decode_account_id in the patrol.chain_data.event_processor module
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    result = EventProcessor.format_address(["address1"])
    assert result == "decoded_address1"

def test_format_address_exception(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id_error)
    result = EventProcessor.format_address(["address1"])
    # If decode_account_id fails, the method should return the original address
    assert result == "address1"

# -----------------------------
# Tests for process_balance_events
# -----------------------------

def test_process_balance_events(monkeypatch):
    # Patch decode_account_id to control formatting
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    processor = EventProcessor(DummyColdkeyFinder())
    event = {
        "event": {
            "Balances": [
                {"Transfer": {"from": ["addr_from"], "to": ["addr_to"], "amount": 100}},
                {"Withdraw": {"who": ["addr_withdraw"], "amount": 50}},
                {"Deposit": {"who": ["addr_deposit"], "amount": 75}}
            ]
        }
    }
    chain_operations = {"withdrawal": [], "deposit": []}
    result = processor.process_balance_events(event, 123, chain_operations)
    
    # Verify that the Transfer event is formatted and returned.
    assert len(result) == 1
    transfer = result[0]
    assert transfer["coldkey_source"] == "decoded_addr_from"
    assert transfer["coldkey_destination"] == "decoded_addr_to"
    assert transfer["category"] == "balance"
    assert transfer["type"] == "transfer"
    assert transfer["evidence"]["rao_amount"] == 100
    assert transfer["evidence"]["block_number"] == 123

    # Verify that Withdraw and Deposit events were added to chain_operations.
    assert len(chain_operations["withdrawal"]) == 1
    withdrawal = chain_operations["withdrawal"][0]
    assert withdrawal["coldkey_source"] == "decoded_addr_withdraw"
    assert withdrawal["rao_amount"] == 50

    assert len(chain_operations["deposit"]) == 1
    deposit = chain_operations["deposit"][0]
    assert deposit["coldkey_destination"] == "decoded_addr_deposit"
    assert deposit["rao_amount"] == 75

# -------------------------------------
# Tests for process_staking_events (async)
# -------------------------------------

@pytest.mark.asyncio
async def test_process_staking_events_old_format_add(monkeypatch):
    # Test StakeAdded with 2 details (old format)
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeAdded": [["addr_delegate"], 200]}
            ]
        }
    }
    new_format, old_format = await processor.process_staking_events(event, 123)
    # For old format, expect one event.
    assert len(old_format) == 1
    stake_event = old_format[0]
    expected_owner = await dummy_finder.find("decoded_addr_delegate")
    assert stake_event["coldkey_destination"] == expected_owner
    assert stake_event["category"] == "staking"
    assert stake_event["type"] == "add"
    assert stake_event["evidence"]["rao_amount"] == 200
    assert stake_event["evidence"]["block_number"] == 123
    # Note: coldkey_source remains None for old-format add.

@pytest.mark.asyncio
async def test_process_staking_events_new_format_add(monkeypatch):
    # Test StakeAdded with >=5 details (new format)
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeAdded": [["addr_source"], ["addr_delegate"], 300, 10, "net_uid"]}
            ]
        }
    }
    new_format, old_format = await processor.process_staking_events(event, 456)
    # Expect one event in new_format.
    assert len(new_format) == 1
    stake_event = new_format[0]
    expected_owner = await dummy_finder.find("decoded_addr_delegate")
    assert stake_event["coldkey_source"] == "decoded_addr_source"
    assert stake_event["coldkey_destination"] == expected_owner
    assert stake_event["category"] == "staking"
    assert stake_event["type"] == "add"
    evidence = stake_event["evidence"]
    assert evidence["rao_amount"] == 300
    assert evidence["alpha_amount"] == 10
    assert evidence["destination_net_uid"] == "net_uid"
    assert evidence["block_number"] == 456
    assert old_format == []  # Should be empty when new format is used.

@pytest.mark.asyncio
async def test_process_staking_events_stake_removed_old_format(monkeypatch):
    # Test StakeRemoved with 2 details (old format)
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeRemoved": [["addr_delegate"], 150]}
            ]
        }
    }
    new_format, old_format = await processor.process_staking_events(event, 789)
    assert len(old_format) == 1
    stake_event = old_format[0]
    expected_owner = await dummy_finder.find("decoded_addr_delegate")
    assert stake_event["coldkey_source"] == expected_owner
    assert stake_event["category"] == "staking"
    assert stake_event["type"] == "remove"
    assert stake_event["evidence"]["rao_amount"] == 150
    assert stake_event["evidence"]["block_number"] == 789

@pytest.mark.asyncio
async def test_process_staking_events_stake_removed_new_format(monkeypatch):
    # Test StakeRemoved with >=5 details (new format)
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeRemoved": [["addr_destination"], ["addr_delegate"], 250, 20, "net_uid2"]}
            ]
        }
    }
    new_format, old_format = await processor.process_staking_events(event, 101)
    assert len(new_format) == 1
    stake_event = new_format[0]
    expected_owner = await dummy_finder.find("decoded_addr_delegate")
    assert stake_event["coldkey_source"] == expected_owner
    assert stake_event["coldkey_destination"] == "decoded_addr_destination"
    assert stake_event["category"] == "staking"
    assert stake_event["type"] == "remove"
    evidence = stake_event["evidence"]
    assert evidence["rao_amount"] == 250
    assert evidence["alpha_amount"] == 20
    assert evidence["source_net_uid"] == "net_uid2"
    assert evidence["block_number"] == 101
    assert old_format == []

@pytest.mark.asyncio
async def test_process_staking_events_stake_moved(monkeypatch):
    # Test StakeMoved event with exactly 6 details.
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeMoved": [["addr_owner"], ["addr_source"], "net_uid_source", ["addr_destination"], "net_uid_destination", 400]}
            ]
        }
    }
    new_format, old_format = await processor.process_staking_events(event, 202)
    assert len(new_format) == 1
    stake_event = new_format[0]
    expected_source_owner = await dummy_finder.find("decoded_addr_source")
    expected_dest_owner = await dummy_finder.find("decoded_addr_destination")
    assert stake_event["coldkey_owner"] == "decoded_addr_owner"
    assert stake_event["coldkey_source"] == expected_source_owner
    assert stake_event["coldkey_destination"] == expected_dest_owner
    evidence = stake_event["evidence"]
    assert evidence["rao_amount"] == 400
    assert evidence["delegate_hotkey_source"] == "decoded_addr_source"
    assert evidence["delegate_hotkey_destination"] == "decoded_addr_destination"
    assert evidence["source_net_uid"] == "net_uid_source"
    assert evidence["destination_net_uid"] == "net_uid_destination"
    assert evidence["block_number"] == 202

# -----------------------------
# Test for match_old_stake_events
# -----------------------------

def test_match_old_stake_events():
    old_stake_events = [
        {"type": "add", "evidence": {"rao_amount": 100}, "coldkey_source": None},
        {"type": "remove", "evidence": {"rao_amount": 50}, "coldkey_destination": None},
        {"type": "add", "evidence": {"rao_amount": 999}, "coldkey_source": None}
    ]
    chain_operations = {
        "withdrawal": [{"coldkey_source": "withdraw_source", "rao_amount": 100}],
        "deposit": [{"coldkey_destination": "deposit_dest", "rao_amount": 50}]
    }
    matched = EventProcessor.match_old_stake_events(old_stake_events, chain_operations)
    # Only the first two events should be matched.
    assert len(matched) == 2
    for event in matched:
        if event["type"] == "add":
            assert event["coldkey_source"] == "withdraw_source"
        elif event["type"] == "remove":
            assert event["coldkey_destination"] == "deposit_dest"

# -----------------------------
# Tests for parse_events (async)
# -----------------------------

@pytest.mark.asyncio
async def test_parse_events(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    # Create an event with both balance and staking events.
    event = {
        "event": {
            "Balances": [
                {"Transfer": {"from": ["addr_from"], "to": ["addr_to"], "amount": 100}},
                {"Withdraw": {"who": ["addr_withdraw"], "amount": 50}}
            ],
            "SubtensorModule": [
                {"StakeAdded": [["addr_source"], "addr_delegate", 300, 10, "net_uid"]}
            ]
        }
    }
    events_list = [event]
    result = await processor.parse_events(events_list, 500, asyncio.Semaphore(1))
    # Expect two events from processing:
    # - A transfer event (balance)
    # - A staking event from new format (StakeAdded)
    transfer_events = [e for e in result if e["type"] == "transfer"]
    stake_events = [e for e in result if e["type"] == "add"]
    assert len(transfer_events) == 1
    assert len(stake_events) == 1

# -----------------------------
# Tests for process_event_data (async)
# -----------------------------

@pytest.mark.asyncio
async def test_process_event_data(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_processor.decode_account_id", dummy_decode_account_id)
    dummy_finder = DummyColdkeyFinder()
    processor = EventProcessor(dummy_finder)
    # Prepare event_data with multiple blocks and error cases.
    event_data = {
        "100": [
            {
                "event": {
                    "Balances": [
                        {"Transfer": {"from": ["addr_from"], "to": ["addr_to"], "amount": 100}}
                    ]
                }
            }
        ],
        "invalid_block": [
            {"event": {}}
        ],
        "200": "not a list"
    }
    result = await processor.process_event_data(event_data)
    # Block "100" should process correctly, so there should be at least one transfer event.
    assert any(e["type"] == "transfer" for e in result)
    
    # Test non-dict input returns empty list.
    result_non_dict = await processor.process_event_data("not a dict")
    assert result_non_dict == []
    
    # Test empty dict returns empty list.
    result_empty = await processor.process_event_data({})
    assert result_empty == []