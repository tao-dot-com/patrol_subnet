import asyncio
from typing import Optional
from websockets.asyncio import client

from async_substrate_interface import AsyncSubstrateInterface
from async_substrate_interface.async_substrate import Websocket

class CustomWebsocket(Websocket):
    def __init__(
        self,
        ws_url: str,
        max_subscriptions=1024,
        max_connections=100,
        shutdown_timer=5,
        options: Optional[dict] = None,
    ):
        """
        CustomWebsocket that allows overriding of connection parameters and ensures
        that self._initialized is set only after self.ws is successfully connected.
        """
        # Pass all arguments to the base __init__
        super().__init__(ws_url, max_subscriptions, max_connections, shutdown_timer, options)

    async def connect(self, force=False):
        """
        Overridden connection logic.
        
        Instead of setting self._initialized to True before establishing the websocket connection,
        we move the assignment to after self.ws is successfully set.
        """
        if self._exit_task:
            self._exit_task.cancel()
        if not self._initialized or force:
            try:
                # Attempt to cancel any existing receiving task and close the current websocket if available.
                if self._receiving_task:
                    self._receiving_task.cancel()
                    await self._receiving_task
                if self.ws:
                    await self.ws.close()
            except (AttributeError, asyncio.CancelledError):
                pass

            self.ws = await asyncio.wait_for(
                client.connect(self.ws_url, **self._options), timeout=10
            )
            self._receiving_task = asyncio.create_task(self._start_receiving())
            self._initialized = True

class CustomAsyncSubstrateInterface(AsyncSubstrateInterface):
    def __init__(self, url=None, ws=None, **kwargs):
        """
        Extends AsyncSubstrateInterface to allow injecting a custom websocket connection.
        
        Args:
            url: the URI of the chain to connect to.
            ws: Optional websocket connection to use. If provided, it overrides the default one.
            **kwargs: any additional keyword arguments for the parent class.
        """
        # Initialize the parent class with all normal parameters.
        super().__init__(url, **kwargs)
        # Override the websocket connection if one is provided.
        self.ws = ws