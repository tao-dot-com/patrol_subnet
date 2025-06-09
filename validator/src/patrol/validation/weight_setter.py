import logging

from bittensor_wallet.bittensor_wallet import Wallet

from patrol.validation import TaskType
from patrol.validation.scoring import MinerScoreRepository
from bittensor.core.async_subtensor import AsyncSubtensor

logger = logging.getLogger(__name__)

class WeightSetter:

    def __init__(self,
                 miner_score_repository: MinerScoreRepository,
                 subtensor: AsyncSubtensor,
                 wallet: Wallet,
                 net_uid: int,
                 task_weights: dict[TaskType, float]
    ):
        self.miner_score_repository = miner_score_repository
        self.subtensor = subtensor
        self.wallet = wallet
        self.net_uid = net_uid
        self.task_weights = task_weights

    async def calculate_weights(self):
        metagraph = await self.subtensor.metagraph(self.net_uid)
        miners = list(zip(metagraph.hotkeys, metagraph.uids.tolist()))

        #overall_coldkey_search_scores = await self.miner_score_repository.find_last_average_overall_scores(TaskType.COLDKEY_SEARCH)
        #weighted_coldkey_search_scores = {k: v * self.task_weights[TaskType.COLDKEY_SEARCH] for k, v in overall_coldkey_search_scores.items() if k in miners}

        overall_hotkey_ownership_scores = await self.miner_score_repository.find_last_average_overall_scores(TaskType.HOTKEY_OWNERSHIP)
        registered_overall_hotkey_ownership_scores = {k: v for k, v in overall_hotkey_ownership_scores.items() if k in miners}
        total_hotkey_ownership_scores = sum(registered_overall_hotkey_ownership_scores.values())
        hotkey_weighting = self.task_weights[TaskType.HOTKEY_OWNERSHIP] if total_hotkey_ownership_scores else 0

        #hotkey_ownership_weights = {k: v/total_hotkey_ownership_scores for k, v in registered_overall_hotkey_ownership_scores.items()} if total_hotkey_ownership_scores else {}

        overall_stake_predict_scores = await self.miner_score_repository.find_latest_stake_prediction_overall_scores()
        registered_overall_stake_predict_scores = {k: v for k, v in overall_stake_predict_scores.items() if k in miners}
        total_stake_predict_scores = sum(registered_overall_stake_predict_scores.values())
        prediction_weighting = self.task_weights[TaskType.PREDICT_ALPHA_SELL] if total_stake_predict_scores else 0

        #stake_predict_weights = {k: v/total_stake_predict_scores for k, v in registered_overall_stake_predict_scores.items()} if total_stake_predict_scores else {}

        overall_weights = {}
        for key in set(registered_overall_hotkey_ownership_scores) | set(registered_overall_stake_predict_scores):
            hotkey_weight = registered_overall_hotkey_ownership_scores.get(key, 0.0) / total_hotkey_ownership_scores if total_hotkey_ownership_scores else 0
            prediction_weight  = registered_overall_stake_predict_scores.get(key, 0.0) / total_stake_predict_scores if total_stake_predict_scores else 0

            overall_weight = (hotkey_weighting * hotkey_weight + prediction_weighting * prediction_weight) / (hotkey_weighting + prediction_weighting)
            overall_weights[key] = overall_weight

        # for key in set(hotkey_ownership_weights) | set(registered_overall_stake_predict_scores):
        #     overall_weights[key] = (
        #         hotkey_weight * hotkey_ownership_weights.get(key, 0.0) +
        #         prediction_weight * stake_predict_weights.get(key, 0.0)
        #     ) / (hotkey_weight + prediction_weight)


        #weighted_overall_stake_predict_scores = {k: v * self.task_weights[TaskType.PREDICT_ALPHA_SELL] for k, v in overall_stake_predict_scores.items() if k in miners}
        # TODO: Transform stake_predict_scores to normalized values

        # overall_scores = {}
        # for key in set(weighted_overall_stake_predict_scores) | set(weighted_hotkey_ownership_scores):
        #     overall_scores[key] = weighted_overall_stake_predict_scores.get(key, 0) + weighted_hotkey_ownership_scores.get(key, 0)
        #
        # sum_of_scores = sum(overall_scores.values())
        # if sum_of_scores == 0:
        #     return {}
        #
        # overall_weights = {k: v / sum_of_scores for k, v in overall_scores.items()}
        return overall_weights

    async def set_weights(self, weights: dict[tuple[str, int], float]):
        if not weights:
            logger.info("No weights to set.")
            return

        _, uids = zip(*weights.keys())

        weight_values = list(weights.values())
        uid_values = list(uids)

        await self.subtensor.set_weights(wallet=self.wallet, netuid=self.net_uid, uids=uid_values, weights=weight_values)
        weights_for_logging = {str(k): v for k, v in weights.items()}
        logger.info("Set weights", extra=weights_for_logging)

    async def is_weight_setting_due(self) -> bool:
        my_hotkey = self.wallet.get_hotkey().ss58_address
        my_uid = await self.subtensor.get_uid_for_hotkey_on_subnet(my_hotkey, self.net_uid)

        blocks_since_last_update = await self.subtensor.blocks_since_last_update(self.net_uid, my_uid)
        tempo = await self.subtensor.tempo(self.net_uid)

        return blocks_since_last_update > tempo
