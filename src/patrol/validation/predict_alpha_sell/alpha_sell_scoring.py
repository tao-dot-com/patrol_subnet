from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeRepository, \
    AlphaSellEventRepository, TransactionType
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellValidator
from patrol.validation.scoring import MinerScore, MinerScoreRepository


class AlphaSellScoring:

    def __init__(
            self, challenge_repository: AlphaSellChallengeRepository,
            miner_score_repository: MinerScoreRepository,
            chain_reader: ChainReader,
            alpha_sell_event_repository: AlphaSellEventRepository
    ):
        self.challenge_repository = challenge_repository
        self.miner_score_repository = miner_score_repository
        self.chain_reader = chain_reader
        self.alpha_sell_event_repository = alpha_sell_event_repository

    async def get_miner_scores(self):
        upper_block = (await self.chain_reader.get_current_block()) - 1

        for scorable_challenge_batch in await self.challenge_repository.find_scorable_challenges(upper_block):
            validator = await AlphaSellValidator.create(scorable_challenge_batch, self.alpha_sell_event_repository)
            scorable_tasks = await self.challenge_repository.find_tasks(scorable_challenge_batch.batch_id)
            await self._score_tasks(validator, scorable_tasks)

    async def _score_tasks(self, validator, tasks: list[AlphaSellChallengeTask]):
        for task in tasks:
            accuracy = validator.score_miner(task)
            miner_score = MinerScore()

