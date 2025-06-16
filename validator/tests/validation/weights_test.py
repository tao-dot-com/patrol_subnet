from unittest.mock import AsyncMock, MagicMock

from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet.bittensor_wallet import Wallet

from patrol.validation import TaskType
from patrol.validation.scoring import MinerScoreRepository
from patrol.validation.weight_setter import WeightSetter
from bittensor.core.async_subtensor import AsyncSubtensor
import numpy as np
from pytest import approx

async def test_skip_weights():
    pass

async def test_calculate_weights_with_hotkey_ownership_scores_only():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    hotkey_ownership_scores = {
        ("alice", 1): 5.0,
        ("bob", 2): 1.5,
        ("carol", 2): 1.0,
        ("dave", 4): 6.0,
    }

    mock_score_repository.find_last_average_overall_scores.return_value = hotkey_ownership_scores
    mock_score_repository.find_latest_stake_prediction_overall_scores.return_value = {}

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    sum_of_scores_weighted = (60 * (sum(hotkey_ownership_scores.values()) - 1.5)) # No Bob!

    task_weights = {
        #TaskType.COLDKEY_SEARCH: 50,
        TaskType.HOTKEY_OWNERSHIP: 60,
        TaskType.PREDICT_ALPHA_SELL: 40,
    }

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81, task_weights)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 1
    assert weights == {
        ("alice", 1): (5.0 * 60) / sum_of_scores_weighted,
        ("carol", 2): (1.0 * 60)  / sum_of_scores_weighted,
        ("dave", 4):  (6.0 * 60) / sum_of_scores_weighted,
    }


async def test_calculate_weights_with_stake_prediction_scores_only():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    stake_prediction_scores = {
        ("alice", 1): 5.0,
        ("bob", 2): 1.5,
        ("carol", 2): 1.0,
        ("dave", 4): 6.0,
    }

    mock_score_repository.find_last_average_overall_scores.return_value = {}
    mock_score_repository.find_latest_stake_prediction_overall_scores.return_value = stake_prediction_scores

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    score_to_subtract = 1.0 * 0.9
    sum_of_scores_weighted = sum((sc - score_to_subtract) for sc in [5.0, 1.0, 6.0]) # No Bob!

    task_weights = {
        #TaskType.COLDKEY_SEARCH: 50,
        TaskType.HOTKEY_OWNERSHIP: 60,
        TaskType.PREDICT_ALPHA_SELL: 40,
    }

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81, task_weights)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 1
    assert len(weights) == 3
    assert weights[("alice", 1)] == approx(((5.0 - score_to_subtract) * 40) / (40 * sum_of_scores_weighted))
    assert weights[("carol", 2)] == approx(((1.0 - score_to_subtract) * 40) / (40 * sum_of_scores_weighted))
    assert weights[("dave", 4)]  == approx(((6.0 - score_to_subtract) * 40) / (40 *sum_of_scores_weighted))


async def test_calculate_weights_with_scores_for_both_tasks():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    stake_prediction_scores = {
        ("alice", 1): 500,
        ("bob", 2): 150,
        ("carol", 2): 100,
        ("dave", 4): 600,
    }

    hotkey_ownership_scores = {
        ("alice", 1): 1,
        ("bob", 2): 1,
        ("carol", 2): 1,
        ("dave", 4): 1,
    }

    mock_score_repository.find_last_average_overall_scores.return_value = hotkey_ownership_scores
    mock_score_repository.find_latest_stake_prediction_overall_scores.return_value = stake_prediction_scores

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    score_to_subtract = 100 * 0.9
    sum_of_prediction_scores = sum((sc - score_to_subtract) for sc in [500, 100, 600]) # No Bob!

    sum_of_hotkey_ownership_scores = sum(hotkey_ownership_scores.values()) - 1 # No Bob!

    task_weights = {
        #TaskType.COLDKEY_SEARCH: 50,
        TaskType.HOTKEY_OWNERSHIP: 60,
        TaskType.PREDICT_ALPHA_SELL: 40,
    }

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81, task_weights)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 1
    assert weights == {
        ("alice", 1): (40 * ((500 - score_to_subtract) / sum_of_prediction_scores) + (60 * 1.0 / sum_of_hotkey_ownership_scores)) / 100,
        ("carol", 2): (40 * ((100 - score_to_subtract) / sum_of_prediction_scores) + (60 * 1.0 / sum_of_hotkey_ownership_scores)) / 100,
        ("dave", 4):  (40 * ((600 - score_to_subtract) / sum_of_prediction_scores) + (60 * 1.0 / sum_of_hotkey_ownership_scores)) / 100,
    }


async def test_calculate_weights_with_no_existing_scores():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    mock_score_repository.find_last_average_overall_scores.return_value = {}
    mock_score_repository.find_latest_stake_prediction_overall_scores.return_value = {}

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    task_weights = {
        TaskType.COLDKEY_SEARCH: 80,
        TaskType.HOTKEY_OWNERSHIP: 20,
    }

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81, task_weights)

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

    weight_setter = WeightSetter(mock_score_repository, mock_subtensor, wallet, 81, {})
    await weight_setter.set_weights(weights)

    mock_subtensor.set_weights.assert_awaited_once_with(
        wallet=wallet, netuid=81, uids=[2, 3, 5, 23], weights=[0.3, 0.1, 0.4, 0.2]
    )

async def test_set_no_weights():

    weights = {}
    mock_score_repository = AsyncMock(MinerScoreRepository)

    wallet = MagicMock(Wallet)
    mock_subtensor = AsyncMock(AsyncSubtensor)

    weight_setter = WeightSetter(mock_score_repository, mock_subtensor, wallet, 81, {})
    await weight_setter.set_weights(weights)

    mock_subtensor.set_weights.assert_not_awaited()
