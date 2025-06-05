from unittest.mock import AsyncMock, MagicMock

from bittensor.core.metagraph import AsyncMetagraph
from bittensor_wallet.bittensor_wallet import Wallet

from patrol.validation import TaskType
from patrol.validation.scoring import MinerScoreRepository
from patrol.validation.weight_setter import WeightSetter
from bittensor.core.async_subtensor import AsyncSubtensor
import numpy as np

async def test_skip_weights():
    pass

async def test_calculate_weights():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    coldkey_search_scores = {
        ("alice", 1): 10.0,
        ("bob", 2): 3.0,
        ("carol", 2): 2.0,
        ("dave", 4): 12.0,
        ("emily", 6): 7.0
    }
    hotkey_ownership_scores = {
        ("alice", 1): 5.0,
        ("bob", 2): 1.5,
        ("carol", 2): 1.0,
        ("dave", 4): 6.0,
    }

    def last_average_overall_scores(task_type: TaskType):
        return coldkey_search_scores if task_type == TaskType.COLDKEY_SEARCH else hotkey_ownership_scores

    mock_score_repository.find_last_average_overall_scores = AsyncMock(side_effect=last_average_overall_scores)

    mock_subtensor = AsyncMock(AsyncSubtensor)
    mock_metagraph = AsyncMock(AsyncMetagraph)
    mock_subtensor.metagraph.return_value = mock_metagraph

    mock_metagraph.uids = np.array([1, 2, 4, 6])

    mock_metagraph.hotkeys = ["alice", "carol", "dave", "emily"]

    sum_of_scores_weighted = (80 * (sum(coldkey_search_scores.values()) - 3.0)) + (20 * (sum(hotkey_ownership_scores.values()) - 1.5)) # No Bob!

    task_weights = {
        TaskType.COLDKEY_SEARCH: 80,
        TaskType.HOTKEY_OWNERSHIP: 20,
    }

    weights = WeightSetter(mock_score_repository, mock_subtensor, MagicMock(Wallet), 81, task_weights)

    weights = await weights.calculate_weights()

    assert sum(weights.values()) == 1
    assert weights == {
        ("alice", 1): (10.0 * 80 + 5.0 * 20) / sum_of_scores_weighted,
        ("carol", 2): (2.0 * 80 + 1.0 * 20)  / sum_of_scores_weighted,
        ("dave", 4):  (12.0 * 80 + 6.0 * 20) / sum_of_scores_weighted,
        ("emily", 6): (7.0 * 80)  / sum_of_scores_weighted
    }

async def test_calculate_weights_with_no_existing_scores():

    mock_score_repository = AsyncMock(MinerScoreRepository)

    mock_score_repository.find_last_average_overall_scores.return_value = {}

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
