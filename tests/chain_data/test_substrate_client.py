import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from patrol.chain_data.substrate_client import SubstrateClient, GROUP_INIT_BLOCK


# ---------------------------
# Test: initialize_connections
# ---------------------------
@pytest.mark.asyncio
async def test_initialize_connections():
    # Create a fake substrate object.
    fake_substrate = MagicMock()
    fake_substrate.get_block_hash = AsyncMock(return_value="fake_hash")
    fake_substrate.init_runtime = AsyncMock(return_value=None)
    
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url", keepalive_interval=0.1, max_retries=3)
    # Patch _create_connection to always return our fake substrate.
    client._create_connection = AsyncMock(return_value=fake_substrate)
    
    await client.initialize_connections()
    
    # Check that each group in GROUP_INIT_BLOCK now has a connection.
    for group in GROUP_INIT_BLOCK:
        assert group in client.connections
        assert client.connections[group] == fake_substrate


# ---------------------------
# Test: get_connection (when already present)
# ---------------------------
@pytest.mark.asyncio
async def test_get_connection_when_present():
    fake_substrate = MagicMock()
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url")
    client.connections[1] = fake_substrate
    
    substrate = await client.get_connection(1)
    assert substrate == fake_substrate


# ---------------------------
# Test: get_connection (when missing)
# ---------------------------
@pytest.mark.asyncio
async def test_get_connection_when_missing():
    fake_substrate = MagicMock()
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url")
    # Patch _reinitialize_connection to return our fake substrate.
    client._reinitialize_connection = AsyncMock(return_value=fake_substrate)
    
    substrate = await client.get_connection(1)
    assert substrate == fake_substrate
    # Also, the connection should be stored.
    assert client.connections[1] == fake_substrate


# ---------------------------
# Test: query (successful query)
# ---------------------------
@pytest.mark.asyncio
async def test_query_success():
    fake_substrate = MagicMock()
    # Create a fake async method for get_block_hash.
    fake_method = AsyncMock(return_value="fake_block_hash")
    setattr(fake_substrate, "get_block_hash", fake_method)
    
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url")
    client.connections[1] = fake_substrate
    
    result = await client.query(1, "get_block_hash", 3784340)
    fake_method.assert_awaited_once_with(3784340)
    assert result == "fake_block_hash"


# ---------------------------
# Test: query (invalid group)
# ---------------------------
@pytest.mark.asyncio
async def test_query_invalid_group():
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url")
    with pytest.raises(Exception) as excinfo:
        await client.query(999, "get_block_hash", 3784340)
    assert "not initialized" in str(excinfo.value)


# ---------------------------
# Test: query (failure after retries)
# ---------------------------
@pytest.mark.asyncio
async def test_query_failure_after_retries():
    fake_substrate = MagicMock()
    # Simulate a query method that always fails.
    fake_method = AsyncMock(side_effect=Exception("Test failure"))
    setattr(fake_substrate, "get_block_hash", fake_method)
    
    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url", keepalive_interval=0.1, max_retries=2)
    client.connections[1] = fake_substrate
    # Patch _reinitialize_connection to return our fake substrate as well.
    client._reinitialize_connection = AsyncMock(return_value=fake_substrate)
    
    with pytest.raises(Exception) as excinfo:
        await client.query(1, "get_block_hash", 3784340)
    assert "Query failed" in str(excinfo.value)


# ---------------------------
# Test: _keepalive_task (reinitialization on failure)
# ---------------------------
@pytest.mark.asyncio
async def test_keepalive_reinitialization():
    fake_substrate = MagicMock()
    # Simulate failure on the first call to get_block.
    fake_get_block = AsyncMock(side_effect=[Exception("fail"), "success"])
    fake_substrate.get_block = fake_get_block

    client = SubstrateClient(GROUP_INIT_BLOCK, "dummy_url", keepalive_interval=0.1, max_retries=2)
    # Patch _reinitialize_connection so we can detect its call.
    client._reinitialize_connection = AsyncMock(return_value=fake_substrate)
    
    # Run the keepalive task for a short period.
    task = asyncio.create_task(client._keepalive_task(1, fake_substrate))
    # Let the task run for a short while (enough for a couple of iterations).
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Ensure that get_block was called and that _reinitialize_connection was invoked due to the failure.
    fake_get_block.assert_called()
    client._reinitialize_connection.assert_called()