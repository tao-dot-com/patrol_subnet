import pytest
from unittest.mock import AsyncMock, MagicMock
from patrol.chain_data.coldkey_finder import ColdkeyFinder

@pytest.mark.asyncio
async def test_find_calls_query_when_not_cached():
    # Arrange
    fake_query_result = "owner_address_1"
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(return_value=fake_query_result)
    
    finder = ColdkeyFinder(fake_substrate_client)
    hotkey = "hotkey1"
    
    # Act: First call should trigger the substrate query.
    result = await finder.find(hotkey)
    
    # Assert: The result should be what the fake substrate client returns.
    assert result == fake_query_result
    fake_substrate_client.query.assert_awaited_once_with(
        6, "query", "SubtensorModule", "Owner", [hotkey]
    )

@pytest.mark.asyncio
async def test_find_returns_cached_result():
    # Arrange
    fake_query_result = "owner_address_2"
    fake_substrate_client = MagicMock()
    fake_substrate_client.query = AsyncMock(return_value=fake_query_result)
    
    finder = ColdkeyFinder(fake_substrate_client)
    hotkey = "hotkey2"
    
    # Act: First call caches the result.
    result1 = await finder.find(hotkey)
    # Second call should retrieve from cache and not call query again.
    result2 = await finder.find(hotkey)
    
    # Assert: Both results should be equal and the query method was only awaited once.
    assert result1 == fake_query_result
    assert result2 == fake_query_result
    fake_substrate_client.query.assert_awaited_once()

@pytest.mark.asyncio
async def test_find_different_hotkeys_call_query_separately():
    # Arrange
    fake_substrate_client = MagicMock()
    # Setup the fake query to return different values based on input.
    fake_substrate_client.query = AsyncMock(side_effect=lambda group, method, module, func, params: f"owner_for_{params[0]}")
    
    finder = ColdkeyFinder(fake_substrate_client)
    hotkey1 = "hotkeyA"
    hotkey2 = "hotkeyB"
    
    # Act: Call find with two different hotkeys.
    result1 = await finder.find(hotkey1)
    result2 = await finder.find(hotkey2)
    
    # Assert: The query method should have been called once for each distinct hotkey.
    assert result1 == "owner_for_hotkeyA"
    assert result2 == "owner_for_hotkeyB"
    assert fake_substrate_client.query.await_count == 2