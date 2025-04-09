import asyncio
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock
import bittensor as bt
import numpy
from bittensor.core.metagraph import AsyncMetagraph

import pytest
from aiohttp import web
from bittensor_wallet import bittensor_wallet

from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScoreRepository, MinerScore
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.validator import Validator
from patrol.validation.weight_setter import WeightSetter

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
def test_wallet():
    with TemporaryDirectory() as tmp:
        wallet = bittensor_wallet.Wallet(path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

@pytest.fixture
def custom_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_axon(custom_loop):

    async def setup():
        async def handler(request):
            await asyncio.sleep(1)
            return web.json_response(SAMPLE_RESPONSE, status=200, content_type="application/json")

        app = web.Application()
        app.router.add_post("/PatrolSynapse", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        yield runner.addresses[0][0], runner.addresses[0][1]
        await runner.shutdown()
        await site.stop()

    custom_loop.run_until_complete(setup())


async def test_timings_unaffected_by_load(mock_axon, test_wallet):

    ip, port = mock_axon

    dendrite = bt.dendrite(test_wallet)
    target_generator = AsyncMock(TargetGenerator)
    validation_mechanism = AsyncMock(BittensorValidationMechanism)
    scoring_mechanism = AsyncMock(MinerScoring)
    miner_score_repository = AsyncMock(MinerScoreRepository)
    metagraph = AsyncMock(AsyncMetagraph)
    weight_setter = AsyncMock(WeightSetter)

    axon_count = 20
    def on_generate_targets(count: int):
        return [(str(t), t) for t in range(count)]

    mock_generate_targets = AsyncMock(TargetGenerator, side_effect=on_generate_targets)
    target_generator.generate_targets=mock_generate_targets

    validator = Validator(
        validation_mechanism, target_generator, scoring_mechanism, miner_score_repository,
        dendrite, metagraph, uuid.uuid4, weight_setter, enable_weight_setting=True
    )

    metagraph.axons = [bt.axon(test_wallet, port=port, ip=ip).info() for _ in range(axon_count)]
    metagraph.uids = numpy.array(list(range(axon_count)))

    response_times = []
    async def calc_score(*args, **kwargs):
        response_times.append(args[4])

    mock_calc_score = AsyncMock(side_effect=calc_score)
    scoring_mechanism.calculate_score = mock_calc_score

    await validator.query_miner_batch()

    assert len(response_times) == axon_count
    print(response_times)
    for rt in response_times:
        assert 1.0 < rt < 1.1