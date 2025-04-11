import asyncio
import json
import os
import threading
import uuid
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock
import bittensor as bt
import numpy
import uvicorn
from bittensor.core.metagraph import AsyncMetagraph

import pytest
from bittensor_wallet import bittensor_wallet
from fastapi import FastAPI
from starlette.responses import Response

from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScoreRepository
from patrol.validation.target_generation import TargetGenerator
from patrol.validation.validator import Validator
from patrol.validation.weight_setter import WeightSetter

SAMPLE_RESPONSE = json.dumps({
    'subgraph_output': {
        'nodes': [
            {'id': 'node1', 'type': 'wallet', 'origin': 'source1'} for _ in range(500)
        ],
        'edges': [
            {'type': 'transfer', 'source': 'node1', 'destination': 'node2', 'evidence': {'amount': 100, 'block_number': 123}} for i in range(499)
        ]
    }
})

RESPONSE = Response(content=SAMPLE_RESPONSE.encode(), status_code=200, headers={'Content-Type': "application/json"})

app = FastAPI()

@app.post("/PatrolSynapse")
async def handle():
    await asyncio.sleep(1)
    return RESPONSE


@pytest.fixture(scope="session")
def run_test_server():
    host = "127.0.0.1"
    port = 8000
    config = uvicorn.Config(app, host=host, port=port, log_level="error", workers=20)
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(0.5)

    yield host, port
    server.should_exit = True
    thread.join()

@pytest.fixture
def test_wallet():
    with TemporaryDirectory() as tmp:
        wallet = bittensor_wallet.Wallet(path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

@pytest.mark.skipif("CI" in os.environ, reason="Flimsy")
async def test_timings_unaffected_by_load(run_test_server, test_wallet):

    host, port = run_test_server

    dendrite = bt.dendrite(test_wallet)
    target_generator = AsyncMock(TargetGenerator)
    validation_mechanism = AsyncMock(BittensorValidationMechanism)
    scoring_mechanism = AsyncMock(MinerScoring)
    miner_score_repository = AsyncMock(MinerScoreRepository)
    metagraph = AsyncMock(AsyncMetagraph)
    weight_setter = AsyncMock(WeightSetter)

    axon_count = 100
    def on_generate_targets(count: int):
        return [(str(t), t) for t in range(count)]

    mock_generate_targets = AsyncMock(TargetGenerator, side_effect=on_generate_targets)
    target_generator.generate_targets=mock_generate_targets

    validator = Validator(
        validation_mechanism, target_generator, scoring_mechanism, miner_score_repository,
        dendrite, metagraph, uuid.uuid4, weight_setter, enable_weight_setting=True
    )

    metagraph.axons = [bt.axon(test_wallet, port=port, ip=host).info() for _ in range(axon_count)]
    metagraph.uids = numpy.array(list(range(axon_count)))

    response_times = []
    async def calc_score(*args, **kwargs):
        response_times.append(args[4])

    mock_calc_score = AsyncMock(side_effect=calc_score)
    scoring_mechanism.calculate_score = mock_calc_score

    await validator.query_miner_batch()

    print(response_times)
    assert len(response_times) == axon_count
    for rt in response_times:
        assert 1.0 < rt < 1.16