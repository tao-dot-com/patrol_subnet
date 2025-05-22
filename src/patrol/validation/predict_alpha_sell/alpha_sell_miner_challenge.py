import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell import AlphaSellChallenge, PredictionInterval, AlphaSellChallengeRepository
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


class AlphaSellValidator:
    async def validate(self, challenge: AlphaSellChallenge) -> bool:
        return True


class AlphaSellMinerChallenge:

    def __init__(self,
                 batch_id: UUID,
                 subnet_uid: int,
                 hotkeys_ss58: list[str],
                 miner_client: AlphaSellMinerClient,
                 repository: AlphaSellChallengeRepository,
                 prediction_interval: PredictionInterval
    ):
        self.batch_id = batch_id
        self.subnet_uid = subnet_uid
        self.hotkeys_ss58 = hotkeys_ss58
        self.miner_client = miner_client
        self.repository = repository
        self.prediction_interval = prediction_interval

    async def execute_challenge(self, miner: Miner) -> AlphaSellChallenge:
        task_id = uuid.uuid4()
        synapse = AlphaSellSynapse(
            batch_id=str(self.batch_id),
            task_id=str(task_id),
            subnet_uid=self.subnet_uid,
            prediction_interval=self.prediction_interval,
            wallet_hotkeys_ss58=self.hotkeys_ss58,
        )

        response, response_time = await self.miner_client.execute_task(miner.axon_info, synapse)
        now = datetime.now(UTC)
        challenge = AlphaSellChallenge(
            batch_id=self.batch_id,
            subnet_uid=self.subnet_uid,
            hotkeys_ss58=self.hotkeys_ss58,
            prediction_interval=self.prediction_interval,
            task_id=task_id,
            created_at=now,
            predictions=response.predictions,
            response_time_seconds=response_time,
        )

        await self.repository.add(challenge)

        return challenge