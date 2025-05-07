from datetime import datetime, UTC
from unittest.mock import patch

import pytest

from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.chain_data.patrol_websocket import PatrolWebsocket
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.chain.runtime_versions import RuntimeVersions
from patrol.validation.event_store_repository import ChainEvent

runtime_mappings = {
    "150": {
        "block_number_min": 3020542,
        "block_hash_min": "0xd1ea6cbe507a0c13aea36a2dfc9ee55b5806a4b654a2895cbb6bbacb49012382",
        "block_number_max": 3157274,
        "block_hash_max": "0x22088ccf387dc7322082593f78e52d78ff260cbb63be56ff66d7e240f727dafd"
    },
    "261": {
        "block_number_min": 5328896,
        "block_hash_min": "0xd68c6fdc8bfbaf374f38200c93f3ad581606919e6ee208410ffb3e6b911ca9ef",
        "block_number_max": 5413452,
        "block_hash_max": "0x063e166ea94adf9d9267bf6a902864f6196a96ad1d085f0df87a012c73e85b48"
    },
    "244": {
        "block_number_min": 4999898,
        "block_hash_min": "0x994a30a37a116cfe5b985a9c793b02621695341d83b2a2d8d6f47e46e070910f",
        "block_number_max": 5063755,
        "block_hash_max": "0x30812f446b265b06e1634534cb1abf351259244561e465e94f1254a9b964942f"
    },
}

@patch("patrol.validation.chain.chain_reader.datetime")
async def test_read_hotkey_ownership_change_event(mock_datetime):

    now = datetime.now(UTC)
    mock_datetime.now.return_value = now

    substrate_client = SubstrateClient(runtime_mappings, "ws://157.90.13.58:9944", PatrolWebsocket("ws://157.90.13.58:9944"))
    await substrate_client.initialize()
    chain_reader = ChainReader(substrate_client, ColdkeyFinder(substrate_client))

    current_block = 3139365
    runtime_version = RuntimeVersions().runtime_version_for_block(current_block)

    events = list(await chain_reader.find_block_events(runtime_version, [current_block, current_block + 1]))

    assert len(events) == 2

    assert ChainEvent(
        created_at=now, edge_category="SubtensorModule", edge_type="NeuronRegistered",
        coldkey_destination="5Cny5W58EVZuFNEF5YMmYG62SdyAiLovBEhE2vKjgsUV1qFU",
        block_number=3139365
    ) in events

    assert ChainEvent(
        created_at=now, edge_category="SubtensorModule", edge_type="NeuronRegistered",
        coldkey_destination="5CkqxQH6wrXU9krJ9befgMAbpiT1UG1MgW1yjNkoMNHNQJjt",
        block_number=3139366
    ) in events

@pytest.mark.skip()
async def test_find_events_in_batches_of_1000():
    substrate_client = SubstrateClient(runtime_mappings, "ws://157.90.13.58:9944", PatrolWebsocket("ws://157.90.13.58:9944"))
    await substrate_client.initialize()
    chain_reader = ChainReader(substrate_client, ColdkeyFinder(substrate_client))

    #current_block = 3_139_365
    current_block = 5_000_000
    runtime_version = RuntimeVersions().runtime_version_for_block(current_block)

    events = list(await chain_reader.find_block_events(runtime_version, list(range(current_block, current_block + 1000))))
    #assert len(events) == 94

    events = list(await chain_reader.find_block_events(runtime_version, list(range(current_block + 1000, current_block + 2000))))
    #assert len(events) == 107
