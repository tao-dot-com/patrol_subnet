from patrol.validation.scoring import MinerScoreRepository


class HotkeyOwnershipScoring:

    def __init__(self, miner_score_repository: MinerScoreRepository):
        self._miner_score_repository = miner_score_repository

    # TODO: Implement this
    async def score(self, something_to_score):
        pass
