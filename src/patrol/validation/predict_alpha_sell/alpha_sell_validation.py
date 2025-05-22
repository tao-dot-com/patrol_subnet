from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.predict_alpha_sell import AlphaSellChallenge, AlphaSellChallengeRepository, \
    ChainStakeEventRepository, TransactionType
from patrol.validation.scoring import MinerScore, MinerScoreRepository


class AlphaSellScoring:

    def __init__(
            self, challenge_repository: AlphaSellChallengeRepository,
            miner_score_repository: MinerScoreRepository,
            chain_reader: ChainReader,
            alpha_sell_event_repository: ChainStakeEventRepository
    ):
        self.challenge_repository = challenge_repository
        self.miner_score_repository = miner_score_repository
        self.chain_reader = chain_reader
        self.alpha_sell_event_repository = alpha_sell_event_repository

    async def get_miner_scores(self, challenge: AlphaSellChallenge):
        upper_block = (await self.chain_reader.get_current_block()) - 1
        unscored_block_ranges = await self.challenge_repository.find_unscored_block_ranges(upper_block)

        for scorable_challenge in await self.challenge_repository.find_scorable_challenges(upper_block):
            pass

    async def _score_batch(self, subnet_uid: int, lower_block: int, upper_block: int):
        stake_removed_events = await self.alpha_sell_event_repository.find_events_by_subnet_uid(subnet_uid, lower_block, upper_block, TransactionType.STAKE_REMOVED.value)
        stake_removed_events = [event for event in events if event.event_type == "StakeRemoved"]





