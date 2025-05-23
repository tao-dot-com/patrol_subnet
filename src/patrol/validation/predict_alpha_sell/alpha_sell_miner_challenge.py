import math
import uuid
from datetime import datetime, UTC
from uuid import UUID

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell import PredictionInterval, AlphaSellChallengeRepository, \
    AlphaSellChallengeBatch, AlphaSellChallengeTask, AlphaSellEventRepository, TransactionType
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse
from patrol.validation.scoring import MinerScore


class AlphaSellValidator:
    def __init__(self, batch: AlphaSellChallengeBatch, stake_removals):
        self.batch = batch
        self.stake_removals = stake_removals

    @classmethod
    async def create(cls, batch: AlphaSellChallengeBatch, event_repository: AlphaSellEventRepository):
        stake_removals = event_repository.find_aggregate_stake_movement_by_hotkey(
            batch.subnet_uid,
            batch.prediction_interval.start_block, batch.prediction_interval.end_block,
            TransactionType.STAKE_REMOVED
        )
        return cls(batch, stake_removals)

    def score_miner(self, task: AlphaSellChallengeTask) -> float:
        predictions_by_hotkey = {p.wallet_hotkey_ss58: p.amount for p in task.predictions}

        accuracies = []

        all_hotkeys = set(predictions_by_hotkey.keys() | self.stake_removals.keys())

        for hk in all_hotkeys:
            predicted = predictions_by_hotkey.get(hk, 0.0)
            actual_amount = self.stake_removals.get(hk, 0.0)
            delta = abs(predicted - actual_amount)

            # if delta == 0:
            #     accuracies.append(1)
            # else:
            accuracy = self.parabolic_accuracy(predicted, actual_amount)
            accuracies.append(accuracy)

        mean_accuracy = sum(accuracies) / len(accuracies)

        return mean_accuracy

    def parabolic_accuracy(self, prediction, actual) -> float:
        error = abs(actual - prediction)
        relative_error = (0.9 * error) / max(2, error)
        ret = 1 - (relative_error ** 2)
        return max(ret, 0.0)

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