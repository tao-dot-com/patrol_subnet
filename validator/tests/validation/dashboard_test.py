import json
import time
from datetime import datetime, UTC
import uuid
from tempfile import TemporaryDirectory

import pytest
from aiohttp import web
from aiohttp.web_request import Request
from bittensor_wallet import Keypair, Wallet

from patrol.validation import TaskType
from patrol.validation.http_.HttpDashboardClient import HttpDashboardClient
from patrol.validation.scoring import MinerScore


@pytest.fixture
async def mock_dashboard(aiohttp_client):

    captured_requests = []

    async def handler(request: Request):
        captured_requests.append({
            "path": request.path,
            "method": request.method,
            "headers": request.headers,
            "body": await request.content.read()
        })

        return web.Response(body=None, status=204)

    app = web.Application()
    app.router.add_put("/patrol/dashboard/api/miner-scores/{id}", handler)
    client = await aiohttp_client(app)
    return client, captured_requests


@pytest.fixture
def mock_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, hotkey_use_password=False, suppress=True)
        yield wallet

async def test_send_scores(mock_dashboard, mock_wallet):

    endpoint, captured_requests = mock_dashboard

    miner_score = MinerScore(
        id=uuid.uuid4(),
        batch_id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        uid=100,
        coldkey="foo",
        hotkey="foobar",
        responsiveness_score=0,
        stake_addition_score=100.5,
        stake_removal_score=112.5,
        overall_score=0.6,
        overall_score_moving_average=0.65,
        validation_passed=False,
        task_type=TaskType.PREDICT_ALPHA_SELL,
        error_message="nope",
        response_time_seconds=1.2,
        novelty_score=None,
        volume_score=0.5,
        volume=0
    )

    dashboard_client = HttpDashboardClient(mock_wallet, f"http://{endpoint.host}:{endpoint.port}")
    await dashboard_client.send_scores([miner_score])

    assert len(captured_requests) == 1
    assert captured_requests[0]["method"] == "PUT"
    assert captured_requests[0]["path"] == f"/patrol/dashboard/api/miner-scores/{miner_score.id}"
    assert captured_requests[0]["headers"]["content-type"] == "application/json"

    token = captured_requests[0]["headers"]["authorization"].rsplit("Bearer ", 1)[-1].split(":")
    assert token[0] == mock_wallet.hotkey.ss58_address
    assert int(token[1]) == pytest.approx(time.time(), rel=10)
    signature = token[2]

    key_pair = Keypair(mock_wallet.hotkey.ss58_address)
    key_pair.verify(token[1], f"0x{signature}")

    body = json.loads(captured_requests[0]["body"].decode())

    assert body["batch_id"] == str(miner_score.batch_id)
    assert datetime.fromisoformat(body["created_at"]) == miner_score.created_at
    assert body["uid"] == miner_score.uid
    assert body["coldkey"] == "foo"
    assert body["hotkey"] == "foobar"
    assert body["stake_added_score"] == 100.5
    assert body["stake_removed_score"] == 112.5
    assert body["overall_score"] == 0.6
    assert body["overall_moving_average_score"] == 0.65
    assert body["is_valid"] == False
    assert body['task_type'] == "PREDICT_ALPHA_SELL"
    assert body["error_message"] == "nope"
