import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from patrol.chain_data.custom_async_substrate_interface import (
    CustomAsyncSubstrateInterface, 
    CustomWebsocket
)

# -------------------------------------------------------------------
# Dummy implementations for testing.

class DummyConnection:
    """A dummy websocket connection to simulate a successful connection."""
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.closed = False

    async def send(self, message):
        # Simulate sending a message.
        return

    async def close(self):
        self.closed = True

    async def recv(self, decode=True):
        # Return a dummy JSON message.
        await asyncio.sleep(0.05)
        return json.dumps({"id": 1, "result": "dummy response"})

# Dummy client module simulation.
class client:
    @staticmethod
    async def connect(ws_url, **options):
        # In real use, this would establish a connection.
        await asyncio.sleep(0.1)
        return DummyConnection(ws_url)

# Dummy AsyncSubstrateInterface base class
class AsyncSubstrateInterface:
    def __init__(self, url=None, **kwargs):
        self.url = url
        self.ws = None

# -------------------------------------------------------------------
# Unit Tests

@pytest.mark.asyncio
@patch("patrol.chain_data.custom_async_substrate_interface.client.connect", new_callable=AsyncMock)
async def test_custom_websocket_successful_connection(mock_connect):
    """
    Test that a successful connection sets self.ws and _initialized properly.
    """
    # Arrange: Set up the dummy connection and configure the mocked connect
    dummy_conn = DummyConnection("ws://dummy")
    mock_connect.side_effect = lambda ws_url, **options: dummy_conn

    # Act: Instantiate and connect the websocket.
    custom_ws = CustomWebsocket("ws://example.com", options={
                        "max_size": 2**32,
                        "write_limit": 2**16,
                    })
    await custom_ws.connect()

    # Assert: Check that the connection is set and _initialized is True.
    assert custom_ws.ws is dummy_conn
    assert custom_ws._initialized is True

@pytest.mark.asyncio
@patch("patrol.chain_data.custom_async_substrate_interface.client.connect", new_callable=AsyncMock)
async def test_custom_websocket_failed_connection(mock_connect):
    """
    Test that if the connection attempt fails, _initialized remains False and ws is None.
    """
    # Arrange: Configure the mocked connect to always raise an exception.
    mock_connect.side_effect = Exception("Connection failed")
    
    # Act: Instantiate the websocket and try to connect, expecting an exception.
    custom_ws = CustomWebsocket("ws://example.com")
    with pytest.raises(Exception, match="Connection failed"):
        await custom_ws.connect()
    
    # Assert: Verify that _initialized remains False and ws is None.
    assert custom_ws._initialized is False
    assert custom_ws.ws is None

@pytest.mark.asyncio
@patch("patrol.chain_data.custom_async_substrate_interface.client.connect", new_callable=AsyncMock)
async def test_issue_fixed_no_stale_state(mock_connect):
    """
    Test to ensure the specific issue is fixed: self._initialized should only be True
    if a valid connection exists (i.e., self.ws is not None).
    """
    # Arrange (first part): Simulate a successful connection.
    dummy_conn = DummyConnection("ws://dummy")
    mock_connect.side_effect = lambda ws_url, **options: dummy_conn
    custom_ws = CustomWebsocket("ws://example.com")

    # Act and Assert (first connection): Check that a good connection sets state correctly.
    await custom_ws.connect()
    assert custom_ws.ws is dummy_conn
    assert custom_ws._initialized is True

    # Arrange (second part): Now configure the mock to simulate a failed connection.
    mock_connect.side_effect = Exception("Connection failed")
    custom_ws_fail = CustomWebsocket("ws://example.com")

    # Act and Assert (failed connection): Expect an exception and verify state.
    with pytest.raises(Exception, match="Connection failed"):
        await custom_ws_fail.connect()
    assert custom_ws_fail.ws is None
    assert custom_ws_fail._initialized is False

@pytest.mark.asyncio
async def test_custom_async_substrate_interface_injects_websocket():
    """
    Test that CustomAsyncSubstrateInterface properly uses an injected websocket connection.
    """
    dummy_ws = CustomWebsocket("ws://example.com")
    iface = CustomAsyncSubstrateInterface(url="ws://dummy", ws=dummy_ws)
    assert iface.ws is dummy_ws