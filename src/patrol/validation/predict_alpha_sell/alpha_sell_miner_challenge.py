import asyncio
import logging
import multiprocessing
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, UTC
from tempfile import TemporaryDirectory

import bittensor as bt
from bittensor import AsyncSubtensor
from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet import Wallet
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.persistence.alpha_sell_challenge_repository import DatabaseAlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellChallengeMiner, PredictionInterval
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


logger = logging.getLogger(__name__)

class AlphaSellValidator:

    def score_miner_accuracy(self, task: AlphaSellChallengeTask, stake_removals: dict[str, float]) -> float:
        predictions_by_hotkey = {p.wallet_hotkey_ss58: p.amount for p in task.predictions}

        all_hotkeys = set(predictions_by_hotkey.keys() | stake_removals.keys())

        square_deltas = []
        total_actual = []

        for hk in all_hotkeys:
            predicted = predictions_by_hotkey.get(hk, 0.0)
            actual_amount = stake_removals.get(hk, 0.0)
            total_actual.append(actual_amount)
            delta = (predicted - actual_amount) ** 2
            square_deltas.append(delta)

        mean_square_deltas = sum(square_deltas) / len(square_deltas)

        accuracy = 1 / (1 + mean_square_deltas)
        return accuracy


class AlphaSellMinerChallenge:

    def __init__(self,
                 miner_client: AlphaSellMinerClient,
    ):
        self.miner_client = miner_client

    async def execute_challenge(self, miner: Miner, batches: list[AlphaSellChallengeBatch]) -> AsyncGenerator[AlphaSellChallengeTask]:
        synapses = [AlphaSellSynapse(
            batch_id=str(batch.batch_id),
            task_id=str(uuid.uuid4()),
            subnet_uid=batch.subnet_uid,
            prediction_interval=batch.prediction_interval,
            wallet_hotkeys_ss58=batch.hotkeys_ss58,
        ) for batch in batches]

        responses = await self.miner_client.execute_tasks(miner.axon_info, synapses)
        for response in responses:
            if isinstance(response, Exception):
                # TODO: Handle exception by assigning an immediate zero score
                logger.warning("Exception during challenge execution: %s", response)
                pass
            else:
                batch_id, task_id, synapse = response
                now = datetime.now(UTC)
                task = AlphaSellChallengeTask(
                    batch_id=batch_id,
                    created_at=now,
                    task_id=task_id,
                    predictions=synapse.predictions,
                    response_time_seconds=0.0,
                    miner=AlphaSellChallengeMiner(miner.axon_info.hotkey, miner.axon_info.coldkey, miner.uid),
                )
                yield task

class AlphaSellMinerChallengeProcess:

    def __init__(self,
                 challenge_repository: AlphaSellChallengeRepository,
                 miner_challenge: AlphaSellMinerChallenge,
                 subtensor: AsyncSubtensor,
                 patrol_metagraph: AsyncMetagraph,
                 interval_window_blocks: int,
                 start_block_offset: int
    ):
        self.challenge_repository = challenge_repository
        self.miner_challenge = miner_challenge
        self.subtensor = subtensor
        self.patrol_metagraph = patrol_metagraph
        self.interval_window_blocks = interval_window_blocks
        self.start_block_offset = start_block_offset

    @classmethod
    async def create(cls,
                     challenge_repository: AlphaSellChallengeRepository,
                     miner_challenge: AlphaSellMinerChallenge,
                     subtensor: AsyncSubtensor,
                     interval_window_blocks: int = 7200,
                     start_block_offset: int = 5,
    ):
        patrol_metagraph = await subtensor.metagraph(81)
        return cls(challenge_repository, miner_challenge, subtensor, patrol_metagraph,
                   interval_window_blocks=interval_window_blocks,
                   start_block_offset=start_block_offset
        )

    async def challenge_miners(self):

        logger.info("Executing Miner Challenges")

        current_block = await self.subtensor.get_current_block()
        start_block = current_block + 5
        prediction_interval = PredictionInterval(start_block, start_block + self.interval_window_blocks)

        await self.patrol_metagraph.sync()
        miners_to_challenge = [Miner(axon, idx) for idx, axon in enumerate(self.patrol_metagraph.axons) if axon.is_serving]

        subnets = await self.subtensor.get_subnets()
        batches = [await self._make_batch(prediction_interval, net_uid) for net_uid in subnets]

        for miner in miners_to_challenge:
            async for task in self.miner_challenge.execute_challenge(miner, batches):
                await self.challenge_repository.add(task)

        logger.info("Miner Challenges complete.")

    async def _make_batch(self, prediction_interval: PredictionInterval, net_uid: int):
        metagraph = await self.subtensor.metagraph(net_uid)
        hotkeys_ss58 = metagraph.hotkeys
        batch_id = uuid.uuid4()
        return AlphaSellChallengeBatch(batch_id, datetime.now(UTC), net_uid, prediction_interval, hotkeys_ss58)


async def run_forever(wallet: Wallet, subtensor: AsyncSubtensor):
    from patrol.validation.config import DB_URL

    engine = create_async_engine(DB_URL)
    challenge_repository = DatabaseAlphaSellChallengeRepository(engine)
    dendrite = bt.Dendrite(wallet)
    miner_client = AlphaSellMinerClient(dendrite)

    miner_challenge = AlphaSellMinerChallenge(miner_client)
    process = await AlphaSellMinerChallengeProcess.create(challenge_repository, miner_challenge, subtensor)

    while True:
        try:
            await process.challenge_miners()
            await asyncio.sleep(3600)
        except Exception as ex:
            logger.exception("Unexpected error")

async def run(wallet: Wallet, subtensor: AsyncSubtensor):
    if subtensor:
        await run_forever(wallet, subtensor)
    else:
        from patrol.validation.config import ARCHIVE_SUBTENSOR
        async with AsyncSubtensor(ARCHIVE_SUBTENSOR) as st:
            await run_forever(wallet, st)


def start_process(wallet: Wallet, subtensor: AsyncSubtensor | None = None):
    def run_async():
        asyncio.run(run(wallet, subtensor))

    process = multiprocessing.Process(target=run_async, daemon=True)
    process.start()
    return process


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        my_wallet = Wallet(name="vali", hotkey="vali", path=tmp)
        my_wallet.create_if_non_existent(coldkey_use_password=False, suppress=True)
        start_process(my_wallet)
