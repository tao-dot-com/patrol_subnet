import os
from datetime import datetime, UTC
from unittest.mock import patch

import pytest

from patrol.chain_data.patrol_websocket import PatrolWebsocket
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.validation.chain import ChainEvent
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.chain.runtime_versions import RuntimeVersions

runtime_mappings = {
    "150": {
        "block_number_min": 3020542,
        "block_hash_min": "0xd1ea6cbe507a0c13aea36a2dfc9ee55b5806a4b654a2895cbb6bbacb49012382",
        "block_number_max": 3157274,
        "block_hash_max": "0x22088ccf387dc7322082593f78e52d78ff260cbb63be56ff66d7e240f727dafd"
    },
    "219": {
        "block_number_min": 4877369,
        "block_hash_min": "0xbe4089bb07518e447d234c27dffd6b0e8ecac6afebce45466d9eb2070e701221",
        "block_number_max": 4920350,
        "block_hash_max": "0x9352d23c47b3f6dc7de623942a9ae0ba14bebb4bb45313a54a8c41c6da16861f"
    },
    "261": {
        "block_number_min": 5328896,
        "block_hash_min": "0xd68c6fdc8bfbaf374f38200c93f3ad581606919e6ee208410ffb3e6b911ca9ef",
        "block_number_max": 5413452,
        "block_hash_max": "0x063e166ea94adf9d9267bf6a902864f6196a96ad1d085f0df87a012c73e85b48"
    },
    "239": {
        "block_number_min": 4943593,
        "block_hash_min": "0xe6657bec2ced4b393a4ab92dedc9d5651b17664fd1925deb222faa5bf75223fe",
        "block_number_max": 4962968,
        "block_hash_max": "0xb6ecb63b37a20c031c50acf3d07073d3b9ccdc3d92e53a3a407d354c76344eb9"
    },
    "240": {
        "block_number_min": 4962969,
        "block_hash_min": "0xa215a0fe55274d71a3d47aec4354e95334cdd5788c194e854cc6dee0223a433e",
        "block_number_max": 4999897,
        "block_hash_max": "0x39860b53bf291ecddd9d5793f4329a3a0fb6b5d345711e869a997f745bf254f3"
    },
    "244": {
        "block_number_min": 4999898,
        "block_hash_min": "0x994a30a37a116cfe5b985a9c793b02621695341d83b2a2d8d6f47e46e070910f",
        "block_number_max": 5063755,
        "block_hash_max": "0x30812f446b265b06e1634534cb1abf351259244561e465e94f1254a9b964942f"
    },
}

# @pytest.fixture(scope="module")
# def event_loop():
#     loop = asyncio.new_event_loop()
#     yield loop
#     loop.close()

ARCHIVE_NODE = os.environ.get('ARCHIVE_NODE')

@pytest.fixture#(scope="module")
async def substrate_client():
    substrate_client = SubstrateClient(runtime_mappings, ARCHIVE_NODE, PatrolWebsocket(ARCHIVE_NODE))
    await substrate_client.initialize()
    return substrate_client


@pytest.mark.skip()
@patch("patrol.validation.chain.chain_reader.datetime")
async def test_read_neuron_registered_events(mock_datetime, substrate_client):

    now = datetime.now(UTC)
    mock_datetime.now.return_value = now

    chain_reader = ChainReader(substrate_client, RuntimeVersions())

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
@patch("patrol.validation.chain.chain_reader.datetime")
async def test_read_coldkey_swap_events(mock_datetime, substrate_client):

    now = datetime.now(UTC)
    mock_datetime.now.return_value = now

    chain_reader = ChainReader(substrate_client, RuntimeVersions())

    current_block = 4905251
    runtime_version = RuntimeVersions().runtime_version_for_block(current_block)

    events = list(await chain_reader.find_block_events(runtime_version, [current_block]))

    assert len(events) == 1

    assert ChainEvent(
        created_at=now, edge_category="SubtensorModule", edge_type='ColdkeySwapScheduled',
        coldkey_source='5CAwB3dSiMC5jJfpvVU47zT3Gyz5ZDoiyHMaYZUuNs5hFh2P',
        coldkey_destination='5HNEheHMipyfrJGfYnKgCfvGsoJnZS2BXQjNz5299jGWZhwg',
        block_number=4905251
    ) in events

    hotkey_swapped = "5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN"
    assert await chain_reader.get_hotkey_owner(hotkey_swapped, 4905251) == "5CAwB3dSiMC5jJfpvVU47zT3Gyz5ZDoiyHMaYZUuNs5hFh2P"
    assert await chain_reader.get_hotkey_owner(hotkey_swapped, 4905251 + 57_445) == "5CAwB3dSiMC5jJfpvVU47zT3Gyz5ZDoiyHMaYZUuNs5hFh2P"
    assert await chain_reader.get_hotkey_owner(hotkey_swapped, 4905251 + 57_445 + 1) == "5HNEheHMipyfrJGfYnKgCfvGsoJnZS2BXQjNz5299jGWZhwg"

@pytest.mark.skip()
async def test_find_hotkey_owner(substrate_client):
    hotkey_swapped = "5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN"

    chain_reader = ChainReader(substrate_client, RuntimeVersions())
    owner = await chain_reader.get_hotkey_owner(hotkey_swapped, 4905251 + 57_445)
    assert owner == "5CAwB3dSiMC5jJfpvVU47zT3Gyz5ZDoiyHMaYZUuNs5hFh2P"

    owner = await chain_reader.get_hotkey_owner(hotkey_swapped, 4905251 + 57_445 + 1)
    assert owner == "5HNEheHMipyfrJGfYnKgCfvGsoJnZS2BXQjNz5299jGWZhwg"


@pytest.mark.skip()
async def test_find_events_in_batches_of_1000(substrate_client):
    chain_reader = ChainReader(substrate_client, RuntimeVersions())

    #current_block = 3_139_365
    current_block = 5_000_000
    runtime_version = RuntimeVersions().runtime_version_for_block(current_block)

    events = list(await chain_reader.find_block_events(runtime_version, list(range(current_block, current_block + 1000))))
    #assert len(events) == 94

    events = list(await chain_reader.find_block_events(runtime_version, list(range(current_block + 1000, current_block + 2000))))
    #assert len(events) == 107
