import asyncio
import os
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

import bittensor as bt
import time
from multiprocessing import Process

import numpy
import pytest
from async_substrate_interface import AsyncSubstrateInterface
from bittensor import AsyncSubtensor, AxonInfo
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet.bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol_mining.miner import Miner
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_batch import HotkeyOwnershipBatch
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, \
    HotkeyOwnershipValidator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.validation.persistence.miner_score_respository import DatabaseMinerScoreRepository

ARCHIVE_NODE = os.environ['ARCHIVE_NODE']

@pytest.fixture
def miner_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="miner", hotkey="miner", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

@pytest.fixture
def vali_wallet():
    with TemporaryDirectory() as tmp:
        wallet = Wallet(name="vali", hotkey="vali", path=tmp)
        wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        yield wallet

@pytest.fixture
def miner_fixture(miner_wallet):
    def boot_miner():
        async def boot_miner_async():
            async with AsyncSubtensor(network="finney") as subtensor:
                miner_service = Miner(
                    dev_flag=True,
                    wallet_path=miner_wallet.path,
                    coldkey=miner_wallet.name,
                    hotkey=miner_wallet.hotkey_str,
                    port=8001,
                    external_ip="192.168.1.100",
                    netuid=81,
                    subtensor=subtensor,
                    min_stake_allowed=3000,
                    network_url=ARCHIVE_NODE,
                    max_future_events=50,
                    max_past_events=50,
                    batch_size=25
                )
            await miner_service.run()

        asyncio.run(boot_miner_async())

    miner = Process(target=boot_miner, daemon=True)
    miner.start()
    time.sleep(80)
    yield miner
    miner.terminate()

@pytest.fixture
async def batch(vali_wallet, miner_wallet):

    dendrite = bt.Dendrite(vali_wallet)
    miner_client = HotkeyOwnershipMinerClient(dendrite)

    #runtime_versions = RuntimeVersions()
    # runtime_versions = RuntimeVersions({"261": {
    #     "block_number_min": 5328896,
    #     "block_hash_min": "0xd68c6fdc8bfbaf374f38200c93f3ad581606919e6ee208410ffb3e6b911ca9ef",
    #     "block_number_max": 5413452,
    #     "block_hash_max": "0x063e166ea94adf9d9267bf6a902864f6196a96ad1d085f0df87a012c73e85b48"
    # }})
    scoring = HotkeyOwnershipScoring()
    #substrate_client = SubstrateClient(runtime_versions.versions, ARCHIVE_NODE, PatrolWebsocket(ARCHIVE_NODE))
    #await substrate_client.initialize()

    substrate = AsyncSubstrateInterface(ARCHIVE_NODE)
    await substrate.initialize()
    chain_reader = ChainReader(substrate)
    validator = HotkeyOwnershipValidator(chain_reader)

    engine = create_async_engine("postgresql+asyncpg://patrol:password@localhost:5432/patrol")
    score_repository = DatabaseMinerScoreRepository(engine)

    target_generator = HotkeyTargetGenerator(substrate)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_metagraph.axons = [AxonInfo(0, "127.0.0.1", 8002, 4, miner_wallet.hotkey.ss58_address, miner_wallet.coldkeypub.ss58_address)]
    mock_metagraph.uids = numpy.array([1])

    challenge = HotkeyOwnershipChallenge(miner_client, scoring, validator, score_repository, None)
    batch = HotkeyOwnershipBatch(challenge, target_generator, mock_metagraph, chain_reader, 4)

    return batch

async def test_run_batch(miner_fixture, batch: HotkeyOwnershipBatch):

    await batch.challenge_miners()
    assert True
