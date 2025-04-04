import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, call

import numpy
import pytest
from bt_decode.bt_decode import AxonInfo
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScoreRepository, MinerScore
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.validator import Validator

import bittensor as bt
from bittensor.core.metagraph import AsyncMetagraph
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
    target_generator = AsyncMock(TargetGenerator)
    metagraph = MagicMock(bt.Metagraph)

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

    validator = Validator(
        validation_mechanism, target_generator, scoring_mechanism, miner_score_repository_mock, dendrite, metagraph, 1, lambda: batch_id
    )
    await validator.query_miner(batch_id, uid, axon.info(), ("bar", 123))

    miner_score_repository_mock.add.assert_awaited_once_with(miner_score)


async def test_query_miner_batch(mock_axon):
    # subtensor = bt.async_subtensor("finney")
    # metagraph = await subtensor.metagraph(81)

    ip, port = mock_axon

    dendrite = bt.dendrite(MockWallet())
    target_generator = AsyncMock(TargetGenerator)
    validation_mechanism = AsyncMock(BittensorValidationMechanism)
    scoring_mechanism = MagicMock(MinerScoring)
    miner_score_repository = AsyncMock(MinerScoreRepository)

    batch_id = uuid.uuid4()

    score_1_uid = uuid.uuid4()
    score_2_uid = uuid.uuid4()

    miner_scores_1 = MinerScore(id=score_1_uid, batch_id=batch_id, uid=3,
                                overall_score=10.0, created_at=datetime.now(UTC),
                                volume_score=1.0, volume=2,
                                responsiveness_score=1.0,
                                response_time_seconds=2.5,
                                novelty_score=1.0, validation_passed=True, error_message=None,
                                coldkey="foo", hotkey="bar")

    miner_scores_2 = MinerScore(id=score_2_uid, batch_id=batch_id, uid=3,
                                overall_score=10.0, created_at=datetime.now(UTC),
                                volume_score=1.0, volume=2,
                                responsiveness_score=1.0,
                                response_time_seconds=2.5,
                                novelty_score=1.0, validation_passed=True, error_message=None,
                                coldkey="foo", hotkey="bar")
    #async def score_1():
    #    return miner_scores_1
    #async def score_2():
    #    return miner_scores_2

    mock_calc_score = AsyncMock(side_effect=[miner_scores_1, miner_scores_1])
    scoring_mechanism.calculate_score = mock_calc_score

    metagraph = AsyncMock(AsyncMetagraph)
    metagraph.axons = [
        bt.axon(MockWallet(), port=port, ip=ip).info(),
        bt.axon(MockWallet(), port=port, ip=ip).info(),
    ]
    metagraph.uids = numpy.array((3, 5),)

    def on_generate_targets(count: int):
        return [("A", 1), ("B", 2)]

    mock_generate_targets = AsyncMock(TargetGenerator, side_effect=on_generate_targets)

    target_generator.generate_targets=mock_generate_targets

    validator = Validator(
        validation_mechanism, target_generator, scoring_mechanism, miner_score_repository,
        dendrite, metagraph, 1, lambda: batch_id
    )

    await validator.query_miner_batch(1)
    miner_score_repository.add.assert_awaited_with(miner_scores_1)
    #     call(miner_scores_1),
    #     call(miner_scores_2),
    # ])
