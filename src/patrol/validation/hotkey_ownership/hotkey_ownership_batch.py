import asyncio
import logging
import uuid

from bittensor.core.metagraph import AsyncMetagraph

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, Miner
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator

logger = logging.getLogger(__name__)

class HotkeyOwnershipBatch:

    def __init__(self,
                 challenge: HotkeyOwnershipChallenge,
                 target_generator: HotkeyTargetGenerator,
                 metagraph: AsyncMetagraph
     ):
        self.challenge = challenge
        self.target_generator = target_generator
        self.metagraph = metagraph

    async def challenge_miners(self):

        batch_id = uuid.uuid4()
        logging_extra = {"batch_id": str(batch_id)}

        logger.info("Batch started", extra=logging_extra)

        axons = self.metagraph.axons
        uids = self.metagraph.uids.tolist()

        miners = list(filter(
            lambda m: m.axon_info.is_serving,
            (Miner(axon, uids[idx]) for idx, axon in enumerate(axons))
        ))

        target_hotkeys = await self.target_generator.generate_targets(len(miners))

        async def challenge(miner):
            try:
                await self.challenge.execute_challenge(miner, target_hotkeys.pop(), batch_id)
            except Exception as ex:
                logger.exception("Unhandled error: %s", ex)

        challenge_tasks = [challenge(miner) for miner in miners]
        await asyncio.gather(*challenge_tasks)

        logger.info("Batch completed", extra=logging_extra)

        return batch_id
