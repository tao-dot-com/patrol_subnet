from uuid import UUID

from bittensor_wallet.bittensor_wallet import Wallet
from patrol.validation.scoring import MinerScoreRepository
from bittensor.core.async_subtensor import AsyncSubtensor

class WeightSetter:

    def __init__(self,
                 miner_score_repository: MinerScoreRepository,
                 subtensor: AsyncSubtensor,
                 wallet: Wallet,
                 net_uid: int
    ):
        self.miner_score_repository = miner_score_repository
        self.subtensor = subtensor
        self.wallet = wallet
        self.net_uid = net_uid

    async def calculate_weights(self, batch_id: UUID):
        overall_scores = await self.miner_score_repository.find_overall_scores_by_batch_id(batch_id)

        sum_of_scores = sum(map(lambda s: s['overall_score'], overall_scores))

        # TODO: take account of historic scores here.

        overall_weights = [{'uid': s['uid'], 'weight': s['overall_score'] / sum_of_scores} for s in overall_scores]

        return overall_weights

    async def set_weights(self, weights: list[dict]):
        uids = [w['uid'] for w in weights]
        weights = [w['weight'] for w in weights]

        await self.subtensor.set_weights(wallet=self.wallet, netuid=self.net_uid, uids=uids, weights=weights)


