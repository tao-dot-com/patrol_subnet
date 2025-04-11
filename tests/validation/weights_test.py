from unittest.mock import AsyncMock, MagicMock

from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet.bittensor_wallet import Wallet

from patrol.validation.scoring import MinerScoreRepository
from patrol.validation.weight_setter import WeightSetter
from bittensor.core.async_subtensor import AsyncSubtensor
import numpy as np

async def test_skip_weights():
    pass

async def test_calculate_weights():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    scores = {
        ("alice", 1): 10.0,
        ("bob", 2): 3.0,
        ("carol", 2): 2.0,
        ("dave", 4): 12.0,
        ("emily", 6): 7.0
    }
    mock_score_repository.find_last_average_overall_scores.return_value = scores

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])
    # async with AsyncSubtensor("finney") as st:
    #     mg = await st.metagraph(81)

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    sum_of_scores = sum(scores.values()) - 3.0 # No Bob!

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 1
    assert weights == {
        ("alice", 1): 10.0/sum_of_scores,
        ("carol", 2): 2.0/sum_of_scores,
        ("dave", 4): 12.0/sum_of_scores,
        ("emily", 6): 7.0/sum_of_scores
    }

async def test_calculate_weights_with_no_existing_scores():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    mock_score_repository.find_last_average_overall_scores.return_value = {}

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])
    # async with AsyncSubtensor("finney") as st:
    #     mg = await st.metagraph(81)

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 0
    assert weights == {}


async def test_set_weights():

    weights = {
        ("alice", 2): 0.3,
        ('bob', 3): 0.1,
        ('carol', 5): 0.4,
        ('dave', 23): 0.2,
    }
    mock_score_repository = AsyncMock(MinerScoreRepository)

    wallet = MagicMock(Wallet)
    mock_subtensor = AsyncMock(AsyncSubtensor)

    weight_setter = WeightSetter(mock_score_repository, mock_subtensor, wallet, 81)
    await weight_setter.set_weights(weights)

    mock_subtensor.set_weights.assert_awaited_once_with(
        wallet=wallet, netuid=81, uids=[2, 3, 5, 23], weights=[0.3, 0.1, 0.4, 0.2]
    )

async def test_set_no_weights():

    weights = {}
    mock_score_repository = AsyncMock(MinerScoreRepository)

    wallet = MagicMock(Wallet)
    mock_subtensor = AsyncMock(AsyncSubtensor)

    weight_setter = WeightSetter(mock_score_repository, mock_subtensor, wallet, 81)
    await weight_setter.set_weights(weights)

    mock_subtensor.set_weights.assert_not_awaited()
