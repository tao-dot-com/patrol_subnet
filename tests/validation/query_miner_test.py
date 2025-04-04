import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock

import pytest
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScoreRepository, MinerScore
from patrol.validation.validator import query_miner

import bittensor as bt
from bittensor_wallet.mock import MockWallet

from aiohttp import web

SAMPLE_RESPONSE = {
    'subgraph_output': {
        'nodes': [
            {'id': 'node1', 'type': 'wallet', 'origin': 'source1'},
            {'id': 'node2', 'type': 'wallet', 'origin': 'source2'}
        ],
        'edges': [
            {'type': 'transfer', 'source': 'node1', 'destination': 'node2', 'evidence': {'amount': 100, 'block_number': 123}}
        ]
    }
}


@pytest.fixture
async def mock_axon():
    app = web.Application()
    async def handler(request):
        return web.json_response(SAMPLE_RESPONSE, status=200, content_type="application/json")

    app.router.add_post("/PatrolSynapse", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    yield runner.addresses[0][0], runner.addresses[0][1]
    await runner.shutdown()
    await site.stop()


async def test_persist_miner_score(mock_axon):
    ip, port = mock_axon

    uid = 12

    miner_score_repository_mock = AsyncMock(MinerScoreRepository)
    validation_mechanism = AsyncMock(BittensorValidationMechanism)
    scoring_mechanism = AsyncMock(MinerScoring)

    batch_id = uuid.uuid4()
    miner_score = MinerScore(id=uuid.uuid4(), batch_id=batch_id, uid=uid,
                             overall_score=10.0, created_at=datetime.now(UTC),
                             volume_score=1.0, volume=2,
                             responsiveness_score=1.0,
                             response_time_seconds=2.5,
                             novelty_score=1.0, validation_passed=True, error_message=None,
                             coldkey="foo", hotkey="bar")

    scoring_mechanism.calculate_score.return_value = miner_score

    dendrite = bt.dendrite(MockWallet())
    axon = bt.axon(MockWallet(), port=port, ip=ip)

    await query_miner(batch_id, uid, dendrite, axon, ("bar", 123), validation_mechanism, scoring_mechanism, miner_score_repository_mock)

    miner_score_repository_mock.add.assert_awaited_once_with(miner_score)