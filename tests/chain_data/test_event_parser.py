import pytest
from unittest.mock import AsyncMock
from patrol.chain_data.event_parser import (
    process_balance_events,
    process_staking_events,
    match_old_stake_events,
    parse_events,
    process_event_data
)

@pytest.mark.asyncio
async def test_process_balance_events_transfer():
    dummy_event = {
        "event": {
            "Balances": [{
                "Transfer": {
                    "from": ["addr1"],
                    "to": ["addr2"],
                    "amount": 1000
                }
            }]
        }
    }
    output = process_balance_events(dummy_event, 100, {"withdrawal": [], "deposit": []})
    assert len(output) == 1
    assert output[0]["type"] == "transfer"
    assert output[0]["evidence"]["block_number"] == 100

@pytest.mark.asyncio
async def test_process_staking_events_new_format():
    coldkey_finder = AsyncMock()
    coldkey_finder.find.return_value = "coldkey123"

    dummy_event = {
        "event": {
            "SubtensorModule": [{
                "StakeAdded": [["owner1"], ["delegate1"], 123, 456, 7]
            }]
        }
    }

    new_format, old_format = await process_staking_events(dummy_event, 101, coldkey_finder)
    assert len(new_format) == 1
    assert new_format[0]["type"] == "add"
    assert new_format[0]["evidence"]["block_number"] == 101
    assert old_format == []

@pytest.mark.asyncio
async def test_match_old_stake_events():
    old_events = [{
        "type": "add",
        "evidence": {"rao_amount": 999, "delegate_hotkey_destination": "del"},
        "coldkey_source": None
    }]
    ops = {"withdrawal": [{"rao_amount": 999, "coldkey_source": "matched_key"}], "deposit": []}
    matched = match_old_stake_events(old_events, ops)
    assert matched[0]["coldkey_source"] == "matched_key"

@pytest.mark.asyncio
async def test_process_event_data_filters_invalid():
    coldkey_finder = AsyncMock()
    event_data = {
        "bad_key": "not_a_list"
    }
    results = await process_event_data(event_data, coldkey_finder)
    assert results == []