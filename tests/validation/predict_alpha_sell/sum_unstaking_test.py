import os
import pytest
from datetime import datetime, UTC
from unittest.mock import patch
from dataclasses import dataclass
from typing import Optional

from patrol.validation.predict_alpha_sell.sum_unstake_events import get_blocks_and_runtime, filter_events, calculate_stake_removed
from patrol.validation.predict_alpha_sell import PredictionInterval, ChainStakeEvent

def test_incorrect_prediction_interval_object():
    """Test that function raises error for incorrectly passed prediction interval"""
    with pytest.raises(AttributeError):
        get_blocks_and_runtime(
            prediction_interval="not a prediction interval",
            current_block=1000,
            runtime_versions={}
        )

def test_no_version_returned():
    """Test behavior when get_version_for_block returns None"""
    with patch('patrol.validation.predict_alpha_sell.sum_unstake_events.get_version_for_block') as mock_get_version:
        mock_get_version.return_value = None
        
        result = get_blocks_and_runtime(
            prediction_interval=PredictionInterval(start_block=1000, end_block=1002),
            current_block=1000,
            runtime_versions={}
        )
        
        assert result == {None: [1000, 1001, 1002]}

def test_single_version():
    """Test behavior when all blocks have the same version"""
    with patch('patrol.validation.predict_alpha_sell.sum_unstake_events.get_version_for_block') as mock_get_version:
        mock_get_version.return_value = "v1"
        
        result = get_blocks_and_runtime(
            prediction_interval=PredictionInterval(start_block=1000, end_block=1002),
            current_block=1000,
            runtime_versions={}
        )
        
        assert result == {"v1": [1000, 1001, 1002]}

def test_two_versions():
    """Test behavior when blocks span two different versions"""
    with patch('patrol.validation.predict_alpha_sell.sum_unstake_events.get_version_for_block') as mock_get_version:
        # Version changes at block 1001
        mock_get_version.side_effect = lambda block, *args: "v1" if block < 1001 else "v2"
        
        result = get_blocks_and_runtime(
            prediction_interval=PredictionInterval(start_block=1000, end_block=1002),
            current_block=1000,
            runtime_versions={}
        )
        
        assert result == {
            "v1": [1000],
            "v2": [1001, 1002]
        }

def test_three_versions():
    """Test behavior when blocks span three different versions"""
    with patch('patrol.validation.predict_alpha_sell.sum_unstake_events.get_version_for_block') as mock_get_version:
        # Version changes at blocks 1001 and 1002
        mock_get_version.side_effect = lambda block, *args: {
            1000: "v1",
            1001: "v2",
            1002: "v3"
        }[block]
        
        result = get_blocks_and_runtime(
            prediction_interval=PredictionInterval(start_block=1000, end_block=1002),
            current_block=1000,
            runtime_versions={}
        )
        
        assert result == {
            "v1": [1000],
            "v2": [1001],
            "v3": [1002]
        }

def test_filter_events_empty_list():
    """Test that function returns empty list when no events match criteria"""
    events = [
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=1,
            source_net_uid=1,
            delegate_hotkey_source="key1"
        ),
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=2,
            source_net_uid=2,
            delegate_hotkey_source="key2"
        )
    ]
    netuid = 3
    hotkeys = ["key3", "key4"]
    
    result = filter_events(events, netuid, hotkeys)
    assert result == []

def test_filter_events_duplicate_events():
    """Test that function returns both events when they match criteria"""
    events = [
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=1,
            source_net_uid=1,
            delegate_hotkey_source="key1"
        ),
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=2,
            source_net_uid=1,
            delegate_hotkey_source="key1"
        )
    ]
    netuid = 1
    hotkeys = ["key1"]
    
    result = filter_events(events, netuid, hotkeys)
    assert len(result) == 2
    assert all(event.source_net_uid == netuid and event.delegate_hotkey_source in hotkeys 
              for event in result)

def test_filter_events_none_hotkey():
    """Test that function excludes events with None delegate_hotkey_source"""
    events = [
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=1,
            source_net_uid=1,
            delegate_hotkey_source="key1"
        ),
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=2,
            source_net_uid=1,
            delegate_hotkey_source=None
        )
    ]
    netuid = 1
    hotkeys = ["key1"]
    
    result = filter_events(events, netuid, hotkeys)
    assert len(result) == 1
    assert result[0].delegate_hotkey_source == "key1"

def test_calculate_stake_removed_empty():
    """Test that function returns empty dict when no StakeRemoved events exist"""
    events = [
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=1,
            source_net_uid=1,
            delegate_hotkey_source="key1",
            rao_amount=100
        ),
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=2,
            source_net_uid=1,
            delegate_hotkey_source="key2",
            rao_amount=200
        )
    ]
    
    result = calculate_stake_removed(events)
    assert result == {}

def test_calculate_stake_removed_sum_amounts():
    """Test that function sums rao_amounts for same delegate_hotkey_source"""
    events = [
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=1,
            source_net_uid=1,
            delegate_hotkey_source="key1",
            rao_amount=100
        ),
        ChainStakeEvent(
            created_at=datetime.now(UTC),
            edge_category="test",
            block_number=2,
            source_net_uid=1,
            delegate_hotkey_source="key1",  # Same hotkey
            rao_amount=200
        )
    ]
    
    result = calculate_stake_removed(events)
    assert result == {"key1": 300}  # 100 + 200