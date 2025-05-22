import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


class AlphaSellValidator:
    async def validate(self, challenge: AlphaSellChallengeBatch) -> bool:
        return True


class AlphaSellMinerChallenge:

    def __init__(self,
                 batch: AlphaSellChallengeBatch,
                 miner_client: AlphaSellMinerClient,
                 repository: AlphaSellChallengeRepository,
    ):
        self.batch = batch
        self.miner_client = miner_client
        self.repository = repository

    async def execute_challenge(self, miner: Miner) -> AlphaSellChallengeTask:
        task_id = uuid.uuid4()
        synapse = AlphaSellSynapse(
            batch_id=str(self.batch.batch_id),
            task_id=str(task_id),
            subnet_uid=self.batch.subnet_uid,
            prediction_interval=self.batch.prediction_interval,
            wallet_hotkeys_ss58=self.batch.hotkeys_ss58,
        )

        response, response_time = await self.miner_client.execute_task(miner.axon_info, synapse)
        now = datetime.now(UTC)
        challenge = AlphaSellChallengeTask(
            batch_id=self.batch.batch_id,
            created_at=now,
            task_id=task_id,
            predictions=response.predictions,
            response_time_seconds=response_time,
            miner=(miner.axon_info.hotkey, miner.uid),
        )

        await self.repository.add(challenge)

        return challenge