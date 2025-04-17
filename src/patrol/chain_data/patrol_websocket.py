import asyncio
import json
import logging
import ssl
import time
from itertools import cycle
from typing import Optional

from websockets import connect, ConnectionClosed

logger = logging.getLogger(__name__)

id_cycle = cycle(range(1, 0xffffff))

async def get_next_id() -> str:
    """
    Generates a pseudo-random ID by returning the next int of a range from 1-998 prepended with
    two random ascii characters.
    """
    id = hex(next(id_cycle))[2:].zfill(6)
    return id


class PatrolWebsocket:
    def __init__(
            self,
            ws_url: str,
            shutdown_timer=5,
            options: Optional[dict] = None,
            cleanup_interval_seconds = 300,
    ):
        """
        Websocket manager object. Allows for the use of a single websocket connection by multiple
        calls.

        Args:
            ws_url: Websocket URL to connect to
            max_subscriptions: Maximum number of subscriptions per websocket connection
            max_connections: Maximum number of connections total
            shutdown_timer: Number of seconds to shut down websocket connection after last use
        """
        self.ws_url = ws_url
        self.ws: Optional["ClientConnection"] = None
        self.shutdown_timer = shutdown_timer
        self._received = {}
        self._in_use = 0
        self._receiving_task = None
        self._expired_requests_cleanup_task = None
        self._attempts = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        self._exit_task = None
        self._options = options if options else {}
        self.last_received = time.time()
        self._cleanup_interval_seconds = cleanup_interval_seconds

    async def __aenter__(self):
        async with self._lock:
            self._in_use += 1
            await self.connect()
        return self

    async def connect(self, force=False):
        if self._exit_task:
            self._exit_task.cancel()
        if not self._initialized or force:
            try:
                self._receiving_task.cancel()
                if self._receiving_task:
                    await self._receiving_task

                self._expired_requests_cleanup_task.cancel()
                await self._expired_requests_cleanup_task

                if self.ws:
                    await self.ws.close()
            except (AttributeError, asyncio.CancelledError):
                pass

            self.ws = await asyncio.wait_for(connect(self.ws_url, **self._options), timeout=10)
            self._receiving_task = asyncio.create_task(self._start_receiving())
            self._initialized = True
            self._expired_requests_cleanup_task = asyncio.create_task(self._cleanup())

    async def _cleanup(self):
        while self._initialized:
            await asyncio.sleep(self._cleanup_interval_seconds)
            oldest = time.time() - self._cleanup_interval_seconds
            logger.info("Expired task cleanup started for %s received responses", len(self._received))
            expired_keys = [k for k, v in self._received.items() if v[0] < oldest]
            for k in expired_keys:
                del self._received[k]
            logger.info("Cleaned up %s expired responses older than %s s", len(expired_keys), self._cleanup_interval_seconds)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:  # TODO is this actually what I want to happen?
            self._in_use -= 1
            if self._exit_task is not None:
                self._exit_task.cancel()
                try:
                    await self._exit_task
                except asyncio.CancelledError:
                    pass
            if self._in_use == 0 and self.ws is not None:
                self._exit_task = asyncio.create_task(self._exit_with_timer())

    async def _exit_with_timer(self):
        """
        Allows for graceful shutdown of websocket connection after specified number of seconds, allowing
        for reuse of the websocket connection.
        """
        try:
            await asyncio.sleep(self.shutdown_timer)
            await self.shutdown()
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        async with self._lock:
            try:
                self._receiving_task.cancel()
                await self._receiving_task

                self._expired_requests_cleanup_task.cancel()
                await self._expired_requests_cleanup_task

                await self.ws.close()
            except (AttributeError, asyncio.CancelledError):
                pass
            finally:
                self._initialized = False
                self.ws = None
                self._receiving_task = None

    async def _recv(self) -> None:
        try:
            # TODO consider wrapping this in asyncio.wait_for and use that for the timeout logic
            response = json.loads(await self.ws.recv(decode=False))
            now = time.time()
            self.last_received = now
            if "id" in response:
                self._received[response["id"]] = (now, response)
            elif "params" in response:
                self._received[response["params"]["subscription"]] = (now, response)
            else:
                raise KeyError(response)
        except ssl.SSLError:
            raise ConnectionClosed
        except (ConnectionClosed, KeyError):
            raise

    async def _start_receiving(self):
        try:
            while True:
                await self._recv()
        except asyncio.CancelledError:
            pass
        except ConnectionClosed:
            async with self._lock:
                await self.connect(force=True)

    async def send(self, payload: dict) -> str:
        """
        Sends a payload to the websocket connection.

        Args:
            payload: payload, generate a payload with the AsyncSubstrateInterface.make_payload method

        Returns:
            id: the internal ID of the request (incremented int)
        """
        # async with self._lock:
        original_id = await get_next_id()

        # self._open_subscriptions += 1
        try:
            await self.ws.send(json.dumps({**payload, **{"id": original_id}}))
            return original_id
        except (ConnectionClosed, ssl.SSLError, EOFError):
            async with self._lock:
                await self.connect(force=True)

    async def retrieve(self, item_id: int) -> Optional[dict]:
        """
        Retrieves a single item from received responses dict queue

        Args:
            item_id: id of the item to retrieve

        Returns:
             retrieved item
        """
        try:
            return self._received.pop(item_id)[1]
        except KeyError:
            await asyncio.sleep(0.001)
            return None
