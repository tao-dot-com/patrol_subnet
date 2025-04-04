import pytest
from unittest.mock import AsyncMock, patch
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.constants import Constants


@pytest.mark.asyncio
async def test_find_caches_result():
    mock_substrate = AsyncMock()
    mock_substrate.query.return_value = "5ColdKeyABC"

    finder = ColdkeyFinder(mock_substrate)
    hotkey = "5HotKey123"

    # First call - should call substrate
    result1 = await finder.find(hotkey)
    assert result1 == "5ColdKeyABC"
    mock_substrate.query.assert_called_once_with('SubtensorModule', 'Owner', [hotkey])

    # Second call - should return cached value, not call substrate again
    result2 = await finder.find(hotkey)
    assert result2 == "5ColdKeyABC"
    mock_substrate.query.assert_called_once()  # still only one query

@pytest.mark.asyncio
async def test_initialize_substrate_connection():
    with patch("patrol.chain_data.coldkey_finder.AsyncSubstrateInterface") as MockInterface:
        mock_instance = AsyncMock()
        MockInterface.return_value = mock_instance

        finder = ColdkeyFinder()
        await finder.initialize_substrate_connection()

        MockInterface.assert_called_once_with(url=Constants.ARCHIVE_NODE_ADDRESS)
        mock_instance.initialize.assert_awaited_once()