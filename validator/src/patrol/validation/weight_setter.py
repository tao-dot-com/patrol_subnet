import logging

from bittensor_wallet.bittensor_wallet import Wallet

from patrol.constants import TaskType
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

        overall_coldkey_search_scores = await self.miner_score_repository.find_last_average_overall_scores(TaskType.COLDKEY_SEARCH)
        weighted_coldkey_search_scores = {k: v * self.task_weights[TaskType.COLDKEY_SEARCH] for k, v in overall_coldkey_search_scores.items() if k in miners}

        overall_hotkey_ownership_scores = await self.miner_score_repository.find_last_average_overall_scores(TaskType.HOTKEY_OWNERSHIP)
        weighted_hotkey_ownership_scores = {k: v * self.task_weights[TaskType.HOTKEY_OWNERSHIP] for k, v in overall_hotkey_ownership_scores.items() if k in miners}

        overall_scores = {}
        for key in set(weighted_coldkey_search_scores) | set(weighted_hotkey_ownership_scores):
            overall_scores[key] = weighted_coldkey_search_scores.get(key, 0) + weighted_hotkey_ownership_scores.get(key, 0)

        sum_of_scores = sum(overall_scores.values())
        if sum_of_scores == 0:
            return {}

        overall_weights = {k: v / sum_of_scores for k, v in overall_scores.items()}
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
