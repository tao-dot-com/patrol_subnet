import pytest
from unittest.mock import AsyncMock
from patrol.chain_data.coldkey_finder import ColdkeyFinder  # replace with actual module name

@pytest.mark.asyncio
async def test_coldkey_finder_caches_result():
    mock_substrate = AsyncMock()
    mock_substrate.query.return_value = '5ColdKeyXYZ'

    finder = ColdkeyFinder(mock_substrate)
    hotkey = '5HotKeyABC'

    # First call triggers substrate.query
    result1 = await finder.find(hotkey)
    assert result1 == '5ColdKeyXYZ'
    mock_substrate.query.assert_called_once_with('SubtensorModule', 'Owner', [hotkey])

    # Second call should hit cache
    result2 = await finder.find(hotkey)
    assert result2 == '5ColdKeyXYZ'
    mock_substrate.query.assert_called_once()  # still only one call