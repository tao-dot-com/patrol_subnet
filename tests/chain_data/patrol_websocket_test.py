import asyncio
import logging
import multiprocessing
import time

import pytest
import uvicorn
from patrol.chain_data.patrol_websocket import PatrolWebsocket
from fastapi import FastAPI, WebSocket

logger = logging.getLogger(__name__)

app = FastAPI()

@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send_delayed_response(data):
        await asyncio.sleep(0.2)
        await websocket.send_json(
            {"id": data["id"], "foo": "bar"})
    try:
        while True:
            data = await websocket.receive_json()
            asyncio.create_task(send_delayed_response(data))

    except Exception as ex:
        #logger.error(f"{ex}")
        try:
            await websocket.close()
        except Exception:
            pass

def run_uvicorn(app: FastAPI, port: int):
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

@pytest.fixture
def websocket_server():
    port = 8081
    process = multiprocessing.Process(target=run_uvicorn, args=(app, port), daemon=True)
    process.start()
    time.sleep(0.5)

    yield f"ws://127.0.0.1:{port}"

    process.terminate()
    process.join()


@pytest.fixture
async def websocket(websocket_server):
    async with PatrolWebsocket(websocket_server, cleanup_interval_seconds=1) as ws:
        yield ws


async def test_handle_concurrent_messages_at_volume(websocket_server, websocket):

    async def receive(id):
        res = await websocket.retrieve(id)
        while res is None:
            await asyncio.sleep(0.0001)
            res = await websocket.retrieve(id)

        return res

    async def send_and_receive():
        id = await websocket.send({"hello": "you"})

        if not id.endswith("1"):
            res = await asyncio.wait_for(receive(id), 2)
            #print(res)
            return res

    requests = 10000

    tasks = [send_and_receive() for _ in range(requests)]
    responses = await asyncio.gather(*tasks)

    assert len(websocket._received) == 625

    await asyncio.sleep(3)

    assert len(websocket._received) == 0
    assert len(responses) == requests
