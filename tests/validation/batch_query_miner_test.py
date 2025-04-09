import asyncio
import threading
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock
import bittensor as bt
import numpy
import uvicorn
from bittensor.core.metagraph import AsyncMetagraph

import pytest
from aiohttp import web
from bittensor_wallet import bittensor_wallet
from fastapi import FastAPI

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

app = FastAPI()

@app.post("/PatrolSynapse")
async def handle():
    await asyncio.sleep(1)
    return SAMPLE_RESPONSE

# @pytest.fixture(scope="session")
# def server_loop():
#     loop = asyncio.new_event_loop()
#     thread = threading.Thread(target=loop.run_forever)
#     thread.start()
#     yield loop
#     loop.call_soon_threadsafe(loop.stop)
#     thread.join()

@pytest.fixture(scope="session")
def run_test_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error", workers=10)
    server = uvicorn.Server(config)

    def start():
        asyncio.run(server.serve())

    threading.Thread(target=start, daemon=True).start()

    #future = asyncio.run_coroutine_threadsafe(start(), server_loop)

    # Give the server a moment to start
    import time
    time.sleep(1)

    #yield "http://127.0.0.1:8000"

    #server.should_exit = True
    #future.cancel()

@pytest.fixture
def test_wallet():
    with TemporaryDirectory() as tmp:
        wallet = bittensor_wallet.Wallet(path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

async def test_timings_unaffected_by_load(run_test_server, test_wallet):

    #ip, port = mock_axon

    dendrite = bt.dendrite(test_wallet)
    target_generator = AsyncMock(TargetGenerator)
    validation_mechanism = AsyncMock(BittensorValidationMechanism)
    scoring_mechanism = AsyncMock(MinerScoring)
    miner_score_repository = AsyncMock(MinerScoreRepository)
    metagraph = AsyncMock(AsyncMetagraph)
    weight_setter = AsyncMock(WeightSetter)

    axon_count = 5
    def on_generate_targets(count: int):
        return [(str(t), t) for t in range(count)]

    mock_generate_targets = AsyncMock(TargetGenerator, side_effect=on_generate_targets)
    target_generator.generate_targets=mock_generate_targets

    validator = Validator(
        validation_mechanism, target_generator, scoring_mechanism, miner_score_repository,
        dendrite, metagraph, uuid.uuid4, weight_setter, enable_weight_setting=True
    )

    metagraph.axons = [bt.axon(test_wallet, port=8000, ip="127.0.0.1").info() for _ in range(axon_count)]
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
        assert 1.0 < rt < 1.2