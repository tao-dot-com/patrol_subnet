import pytest
import time

# Import the functions from your module.
from patrol.chain_data.event_parser import (
    format_address,
    process_balance_events,
    process_staking_events,
    match_old_stake_events,
    parse_events,
    process_event_data,
)

# Dummy logging setup: if needed, override bt.logging methods.
# For example, if bt.logging.error is used, you can override it to do nothing.
# Here we assume bt.logging is already configured.

# ----------------------------
# Tests for format_address
# ----------------------------
def test_format_address_success(monkeypatch):
    # Simulate decode_account_id to return a formatted string.
    def fake_decode(addr):
        return "formatted_" + addr
    monkeypatch.setattr("patrol.chain_data.event_parser.decode_account_id", fake_decode)
    
    # Provide an address list.
    addr = ["test_addr"]
    result = format_address(addr)
    assert result == "formatted_test_addr"

def test_format_address_failure(monkeypatch):
    # Simulate decode_account_id to raise an exception.
    def fake_decode(addr):
        raise Exception("fail")
    monkeypatch.setattr("patrol.chain_data.event_parser.decode_account_id", fake_decode)
    
    addr = ["raw_addr"]
    result = format_address(addr)
    # In case of error, our function returns the first element.
    assert result == "raw_addr"

# ----------------------------
# Tests for process_balance_events
# ----------------------------
@pytest.fixture
def dummy_chain_operations():
    return {"withdrawal": [], "deposit": []}

def test_process_balance_events_transfer(monkeypatch, dummy_chain_operations):
    # Monkeypatch format_address so it simply returns the input prefixed.
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x[0])
    
    event = {
        "event": {
            "Balances": [
                {"Transfer": {
                    "from": ["from_addr"],
                    "to": ["to_addr"],
                    "amount": 1000
                }}
            ]
        }
    }
    block_number = 123
    result = process_balance_events(event, block_number, dummy_chain_operations)
    assert len(result) == 1
    transfer = result[0]
    assert transfer["coldkey_source"] == "formatted_from_addr"
    assert transfer["coldkey_destination"] == "formatted_to_addr"
    assert transfer["category"] == "balance"
    assert transfer["type"] == "transfer"
    assert transfer["evidence"]["rao_amount"] == 1000
    assert transfer["evidence"]["block_number"] == 123

def test_process_balance_events_withdraw_deposit(monkeypatch, dummy_chain_operations):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x[0])
    
    event = {
        "event": {
            "Balances": [
                {"Withdraw": {
                    "who": ["withdraw_addr"],
                    "amount": 500
                }},
                {"Deposit": {
                    "who": ["deposit_addr"],
                    "amount": 700
                }}
            ]
        }
    }
    block_number = 456
    result = process_balance_events(event, block_number, dummy_chain_operations)
    # No formatted events returned for Withdraw/Deposit; they go to chain_operations.
    assert result == []
    assert dummy_chain_operations["withdrawal"] == [{
        "coldkey_source": "formatted_withdraw_addr",
        "rao_amount": 500
    }]
    assert dummy_chain_operations["deposit"] == [{
        "coldkey_destination": "formatted_deposit_addr",
        "rao_amount": 700
    }]

# ----------------------------
# Tests for process_staking_events
# ----------------------------
def test_process_staking_events_old_format(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x[0])
    
    # Old format for StakeAdded and StakeRemoved (length == 2)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeAdded": [
                    ["stakeadd_addr"],
                    2000
                ]},
                {"StakeRemoved": [
                    ["stakeremove_addr"],
                    3000
                ]}
            ]
        }
    }
    block_number = 789
    new_format, old_format = process_staking_events(event, block_number)
    # In old format, new_format should be empty.
    assert new_format == []
    # There should be two old format entries.
    assert len(old_format) == 2
    # Check types and evidence.
    add_event = old_format[0]
    remove_event = old_format[1]
    assert add_event["type"] == "add"
    assert add_event["hotkey_destination"] == "formatted_stakeadd_addr"
    assert add_event["evidence"]["rao_amount"] == 2000
    assert add_event["evidence"]["block_number"] == 789
    assert remove_event["type"] == "remove"
    assert remove_event["hotkey_source"] == "formatted_stakeremove_addr"
    assert remove_event["evidence"]["rao_amount"] == 3000

def test_process_staking_events_new_format(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x)
    
    # New format events (length >= 5 for StakeAdded and StakeRemoved)
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeAdded": [
                    "cold_addr_add", "hot_dest_add", 4000, "alpha_val", "dest_uid"
                ]},
                {"StakeRemoved": [
                    "cold_addr_remove", "hot_source_remove", 5000, "alpha_val2", "source_uid"
                ]}
            ]
        }
    }
    block_number = 1000
    new_format, old_format = process_staking_events(event, block_number)
    assert len(new_format) == 2
    assert old_format == []
    add_event = new_format[0]
    remove_event = new_format[1]
    assert add_event["type"] == "add"
    assert add_event["coldkey_source"] == "formatted_cold_addr_add"
    assert add_event["hotkey_destination"] == "formatted_hot_dest_add"
    assert add_event["evidence"]["rao_amount"] == 4000
    assert add_event["evidence"]["destination_net_uid"] == "dest_uid"
    assert remove_event["type"] == "remove"
    assert remove_event["coldkey_destination"] == "formatted_cold_addr_remove"
    assert remove_event["hotkey_source"] == "formatted_hot_source_remove"
    assert remove_event["evidence"]["rao_amount"] == 5000
    assert remove_event["evidence"]["source_net_uid"] == "source_uid"

def test_process_staking_events_stake_moved(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x)
    
    event = {
        "event": {
            "SubtensorModule": [
                {"StakeMoved": [
                    "cold_addr_move", "hot_source_move", "src_uid", "hot_dest_move", "dest_uid", 6000
                ]}
            ]
        }
    }
    block_number = 1100
    new_format, old_format = process_staking_events(event, block_number)
    # Only new_format should be filled.
    assert len(new_format) == 1
    move_event = new_format[0]
    assert move_event["type"] == "move"
    assert move_event["coldkey_source"] == "formatted_cold_addr_move"
    assert move_event["hotkey_source"] == "formatted_hot_source_move"
    assert move_event["hotkey_destination"] == "formatted_hot_dest_move"
    assert move_event["evidence"]["rao_amount"] == 6000
    assert move_event["evidence"]["source_net_uid"] == "src_uid"
    assert move_event["evidence"]["destination_net_uid"] == "dest_uid"

# ----------------------------
# Tests for match_old_stake_events
# ----------------------------
def test_match_old_stake_events_add(monkeypatch):
    # Prepare an old-format stake add event missing coldkey_source.
    old_stake_events = [{
        "type": "add",
        "coldkey_source": None,
        "hotkey_destination": "dummy",
        "category": "staking",
        "evidence": {"rao_amount": 1000, "block_number": 123}
    }]
    chain_ops = {
        "withdrawal": [{
            "coldkey_source": "balance_from",
            "rao_amount": 1000
        }],
        "deposit": []
    }
    matched = match_old_stake_events(old_stake_events, chain_ops)
    assert len(matched) == 1
    assert matched[0]["coldkey_source"] == "balance_from"

def test_match_old_stake_events_remove(monkeypatch):
    old_stake_events = [{
        "type": "remove",
        "coldkey_destination": None,
        "hotkey_source": "dummy",
        "category": "staking",
        "evidence": {"rao_amount": 2000, "block_number": 123}
    }]
    chain_ops = {
        "withdrawal": [],
        "deposit": [{
            "coldkey_destination": "balance_to",
            "rao_amount": 2000
        }]
    }
    matched = match_old_stake_events(old_stake_events, chain_ops)
    assert len(matched) == 1
    assert matched[0]["coldkey_destination"] == "balance_to"

# ----------------------------
# Tests for parse_events
# ----------------------------
def test_parse_events(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x[0])
    # Create a set of events combining balance and staking events.
    events = [
        # A balance transfer event.
        {
            "event": {
                "Balances": [
                    {"Transfer": {
                        "from": ["from1"],
                        "to": ["to1"],
                        "amount": 111
                    }}
                ]
            }
        },
        # A balance withdraw and deposit events.
        {
            "event": {
                "Balances": [
                    {"Withdraw": {
                        "who": ["withdraw1"],
                        "amount": 222
                    }},
                    {"Deposit": {
                        "who": ["deposit1"],
                        "amount": 333
                    }}
                ]
            }
        },
        # A new-format staking event (StakeAdded).
        {
            "event": {
                "SubtensorModule": [
                    {"StakeAdded": [
                        ["cold_add1"], "hot_dest1", 444, "alpha1", "dest_uid1"
                    ]}
                ]
            }
        },
        # An old-format staking event (StakeRemoved) that will be matched.
        {
            "event": {
                "SubtensorModule": [
                    {"StakeRemoved": [
                        ["stakeremove_old"], 333
                    ]}
                ]
            }
        }
    ]
    block_number = 1000
    # Prepare chain operations: add a matching deposit for the old stake event.
    # For a stake remove old format, we need a matching deposit.
    chain_operations = {"withdrawal": [], "deposit": [{
        "coldkey_destination": "formatted_deposit_for_old",
        "rao_amount": 555
    }]}
    # We can simulate parse_events by first processing the events and then manually
    # extending with match_old_stake_events. Here, we'll monkeypatch process_balance_events and process_staking_events to use our chain_operations.
    result = parse_events(events, block_number)
    # We expect:
    # - 1 transfer event from Balances,
    # - 0 formatted events for withdraw/deposit (but chain_operations updated),
    # - 1 new-format StakeAdded,
    # - 1 old-format StakeRemoved matched via chain_operations.
    # Total formatted events should be 1 (transfer) + 1 (new staking) + 1 (matched old staking) = 3.
    assert len(result) == 3

# ----------------------------
# Tests for process_event_data
# ----------------------------
def test_process_event_data(monkeypatch):
    monkeypatch.setattr("patrol.chain_data.event_parser.format_address", lambda x: "formatted_" + x[0])
    # Create event_data as a dict mapping block numbers (as strings) to lists of events (each block is a list)
    event_data = {
        "100": [
            # Block 100 has one event list with one event (a Transfer)
            {
                "event": {
                    "Balances": [
                        {"Transfer": {
                            "from": ["from_block100"],
                            "to": ["to_block100"],
                            "amount": 777
                        }}
                    ]
                }
            }
        ],
        "200": [
            # Block 200 has one event list with one event (a StakeMoved)
            {
                "event": {
                    "SubtensorModule": [
                        {"StakeMoved": [
                            ["cold_move"], "hot_source", "src_uid", "hot_dest", "dest_uid", 888
                        ]}
                    ]
                }
            }
        ]
    }
    result = process_event_data(event_data)
    print(result)
    # Expect one event from block 100 and one event from block 200.
    assert len(result) == 2
    # Check that the events have the correct evidence block_number.
    for event in result:
        assert event["evidence"]["block_number"] in [100, 200]

def test_process_event_data_invalid(monkeypatch):
    # Passing an invalid type (not a dict) should return empty list.
    result = process_event_data(["not", "a", "dict"])
    assert result == []