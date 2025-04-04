import uuid
from unittest.mock import AsyncMock, MagicMock

from bittensor_wallet.bittensor_wallet import Wallet
from patrol.validation.scoring import MinerScoreRepository
from patrol.validation.weight_setter import WeightSetter
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor_wallet.mock import MockWallet

async def test_skip_weights():
    pass

async def test_calculate_weights():

    batch_id = uuid.uuid4()
    mock_score_repository = AsyncMock(MinerScoreRepository)

    scores = [
        {'hotkey': "alice", 'overall_score': 10, 'uid': 1},
        {'hotkey': "bob", 'overall_score': 3, 'uid': 2},
        {'hotkey': "carol", 'overall_score': 2, 'uid': 3},
        {'hotkey': "dave", 'overall_score': 12, 'uid': 4},
        {'hotkey': "emily", 'overall_score': 7, 'uid': 6},
    ]
    mock_score_repository.find_overall_scores_by_batch_id.return_value = scores

    sum_of_scores = sum([s['overall_score'] for s in scores])

    weights = WeightSetter(mock_score_repository, AsyncMock(AsyncSubtensor), MagicMock(Wallet), 81)

    weights = await weights.calculate_weights(batch_id)
    # assert sum(map(lambda s: weights['weight']) == 1.0
    assert weights[0] == {'uid': 1, 'weight': 10/sum_of_scores}
    assert weights[1] == {'uid': 2, 'weight': 3/sum_of_scores}
    assert weights[2] == {'uid': 3, 'weight': 2/sum_of_scores}
    assert weights[3] == {'uid': 4, 'weight': 12/sum_of_scores}
    assert weights[4] == {'uid': 6, 'weight': 7/sum_of_scores}


async def test_set_weights():

    weights = [
        {'uid': 2, 'weight': 0.3},
        {'uid': 3, 'weight': 0.1},
        {'uid': 5, 'weight': 0.4},
        {'uid': 23, 'weight': 0.2},
    ]
    mock_score_repository = AsyncMock(MinerScoreRepository)

    wallet = MagicMock(Wallet)
    mock_subtensor = AsyncMock(AsyncSubtensor)

    weight_setter = WeightSetter(mock_score_repository, mock_subtensor, wallet, 81)
    await weight_setter.set_weights(weights)

    mock_subtensor.set_weights.assert_awaited_once_with(
        wallet=wallet, netuid=81, uids=[2, 3, 5, 23], weights=[0.3, 0.1, 0.4, 0.2]
    )
