import asyncio
import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.validation.scoring import MinerScoreRepository, MinerScore


class HotkeyOwnershipBatch:

    def __init__(self,
                 challenge: HotkeyOwnershipChallenge,
                 target_generator: HotkeyTargetGenerator,
                 scoring: HotkeyOwnershipScoring,
                 miner_score_repository: MinerScoreRepository
     ):
        self.challenge = challenge
        self.target_generator = target_generator
        self.scoring = scoring
        self.miner_score_repository = miner_score_repository
        self.moving_average_denominator = 20

    async def challenge_miners(self):

        batch_id = uuid.uuid4()

        # Fetch all the miners
        miners = []

        target_hotkeys = await self.target_generator.generate_targets(255)

        async def challenge(miner):
            task_id = uuid.uuid4()
            try:
                response, response_time = await self.challenge.execute_challenge(miner, target_hotkeys.pop())
                score = await self._calculate_score(batch_id, task_id, miner, response_time)
            except AssertionError as ex:
                score = await self._calculate_zero_score(batch_id, task_id, miner, response_time, str(ex))

            await self.miner_score_repository.add(score)

        challenge_tasks = [self.challenge.execute_challenge(miner) for miner in miners]
        await asyncio.gather(*challenge_tasks)



