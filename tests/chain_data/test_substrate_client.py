import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from patrol.chain_data.substrate_client import SubstrateClient, CustomAsyncSubstrateInterface

# ----------------------------
# Fixtures
# ----------------------------

@pytest.fixture
def runtime_mappings():
    return {
        "1": {"block_hash_min": "0xabc"},
        "2": {"block_hash_min": "0xdef"},
    }

@pytest.fixture
def mock_websocket():
    ws = AsyncMock()
    ws.connect = AsyncMock()
    ws.shutdown = AsyncMock()
    return ws

# ----------------------------
# Test: initialize
# ----------------------------

@pytest.mark.asyncio
@patch("patrol.chain_data.substrate_client.PatrolWebsocket", autospec=True)
@patch("patrol.chain_data.substrate_client.CustomAsyncSubstrateInterface", autospec=True)
async def test_initialize_creates_websocket(mock_substrate_cls, mock_ws_cls, runtime_mappings):
    mock_ws = AsyncMock()
    mock_ws_cls.return_value = mock_ws
    mock_substrate = AsyncMock()
    mock_substrate_cls.return_value = mock_substrate

    client = SubstrateClient(runtime_mappings, network_url="wss://mock", websocket=None)
    await client.initialize()

    mock_ws_cls.assert_called_once_with("wss://mock", shutdown_timer=300, options={"max_size": 2**32, "write_limit": 2**16})
    mock_ws.connect.assert_called_once()

    assert len(client.substrate_cache) == len(runtime_mappings)
    for version in runtime_mappings:
        mock_substrate.init_runtime.assert_any_call(block_hash=runtime_mappings[version]["block_hash_min"])
        assert int(version) in client.substrate_cache

# ----------------------------
# Test: query
# ----------------------------

@pytest.mark.asyncio
@patch("patrol.chain_data.substrate_client.CustomAsyncSubstrateInterface", autospec=True)
async def test_query_success(mock_substrate_cls, runtime_mappings):
    substrate = AsyncMock()
    substrate.get_block_hash = AsyncMock(return_value="0x1234")
    mock_substrate_cls.return_value = substrate

    client = SubstrateClient(runtime_mappings, "wss://mock")
    client.substrate_cache = {1: substrate}

    result = await client.query("get_block_hash", runtime_version=1)
    assert result == "0x1234"
    substrate.get_block_hash.assert_called_once()

@pytest.mark.asyncio
@patch("patrol.chain_data.substrate_client.CustomAsyncSubstrateInterface", autospec=True)
async def test_query_uses_default_version(mock_substrate_cls, runtime_mappings):
    substrate = AsyncMock()
    substrate.get_block_hash = AsyncMock(return_value="0x9999")
    mock_substrate_cls.return_value = substrate

    client = SubstrateClient(runtime_mappings, "wss://mock")
    client.substrate_cache = {1: substrate, 2: AsyncMock()}  # Max key is 2
    client.substrate_cache[2].get_block_hash = AsyncMock(return_value="0x9999")

    result = await client.query("get_block_hash")
    assert result == "0x9999"
    client.substrate_cache[2].get_block_hash.assert_called_once()

@pytest.mark.asyncio
@patch("patrol.chain_data.substrate_client.CustomAsyncSubstrateInterface", autospec=True)
async def test_query_fails_and_retries(mock_substrate_cls, runtime_mappings):
    failing_func = AsyncMock(side_effect=Exception("Mock error"))
    substrate = AsyncMock()
    setattr(substrate, "get_block_hash", failing_func)
    mock_substrate_cls.return_value = substrate

    client = SubstrateClient(runtime_mappings, "wss://mock", max_retries=2)
    client.substrate_cache = {1: substrate}

# ----------------------------
# Test: return_runtime_versions
# ----------------------------

def test_return_runtime_versions(runtime_mappings):
    client = SubstrateClient(runtime_mappings, "wss://mock")
    assert client.return_runtime_versions() == runtime_mappings