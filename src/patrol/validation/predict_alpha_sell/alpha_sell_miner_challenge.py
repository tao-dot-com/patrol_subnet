import uuid
from datetime import datetime, UTC

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell import AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellChallengeMiner
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


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
            miner=AlphaSellChallengeMiner(miner.axon_info.hotkey, miner.axon_info.coldkey, miner.uid),
        )

        await self.repository.add(challenge)

        return challenge