import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch, MagicMock

from bittensor import AxonInfo

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellMinerChallenge, AlphaSellValidator
from patrol.validation.predict_alpha_sell import TransactionType, PredictionInterval, \
    AlphaSellPrediction, AlphaSellChallengeRepository, AlphaSellChallengeTask, AlphaSellChallengeBatch
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.uuid")
async def test_challenge_sends_correct_synapse(mock_uuid):
    miner_client = AsyncMock(AlphaSellMinerClient)

    mock_axon_info = MagicMock(AxonInfo)
    mock_axon_info.hotkey = "miner_hk"
    miner = Miner(mock_axon_info, 123)
    batch_id = uuid.uuid4()

    task_id = uuid.uuid4()
    mock_uuid.uuid4.return_value = task_id

    batch = AlphaSellChallengeBatch(
        batch_id=batch_id, subnet_uid=42,
        prediction_interval=PredictionInterval(5_000_000, 5_000_7200),
        hotkeys_ss58=["alice", "bob"],
        created_at=datetime.now(UTC),
    )

    challenge = AlphaSellMinerChallenge(
        batch,
        miner_client,
        AsyncMock(AlphaSellChallengeRepository),
    )

    expected_synapse = AlphaSellSynapse(
        batch_id=str(batch_id), task_id=str(task_id), subnet_uid=42,
        prediction_interval=PredictionInterval(5_000_000, 5_000_7200),
        wallet_hotkeys_ss58=["alice", "bob"]
    )

    miner_client.execute_task.return_value = (expected_synapse, 12.3)

    await challenge.execute_challenge(miner)

    miner_client.execute_task.assert_awaited_once_with(mock_axon_info, expected_synapse)
    miner_client.execute_task.assert_awaited_once_with(mock_axon_info, expected_synapse)


@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.datetime")
@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.uuid.uuid4")
async def test_challenge_miner(mock_uuid, mock_datetime):

    now = datetime.now(UTC)
    task_id = uuid.uuid4()

    mock_datetime.now.return_value = now
    mock_uuid.return_value = task_id

    batch_id = uuid.uuid4()
    subnet_uid = 42
    hotkeys = ["alice", "bob"]
    prediction_interval = PredictionInterval(5_000_000, 5_000_7200)
    predictions = [
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 25.0),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 15.0),
    ]

    miner_client = AsyncMock(AlphaSellMinerClient)
    validator = AsyncMock(AlphaSellValidator)
    validator.validate.return_value = True

    miner_client.execute_task.return_value = (AlphaSellSynapse(
        batch_id=str(batch_id), task_id=str(task_id), subnet_uid=subnet_uid, prediction_interval=prediction_interval,
        wallet_hotkeys_ss58=hotkeys,
        predictions=predictions
    ), 12.3)

    axon = AxonInfo(version=0, ip="192.168.12.1", port=8000, hotkey="miner_hk", coldkey="miner_ck", ip_type=4)
    miner = Miner(axon, 123)

    repository = AsyncMock(AlphaSellChallengeRepository)

    batch = AlphaSellChallengeBatch(batch_id, now, subnet_uid, prediction_interval, hotkeys)

    challenge = AlphaSellMinerChallenge(batch, miner_client, repository)
    response: AlphaSellChallengeTask = await challenge.execute_challenge(miner)

    assert response.batch_id == batch_id
    assert response.created_at == now
    assert response.task_id == task_id
    assert response.predictions == predictions
    assert response.response_time_seconds == 12.3

    repository.add.assert_awaited_once_with(response)