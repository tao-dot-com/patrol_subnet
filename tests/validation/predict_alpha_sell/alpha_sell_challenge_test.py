import uuid
from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

from bittensor import AxonInfo

from patrol.constants import TaskType
from patrol.validation.dashboard import DashboardClient
from patrol.validation.error import MinerTaskException
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import Miner
from patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge import AlphaSellMinerChallenge
from patrol.validation.predict_alpha_sell import TransactionType, PredictionInterval, AlphaSellPrediction, AlphaSellChallengeBatch
from patrol.validation.predict_alpha_sell.alpha_sell_miner_client import AlphaSellMinerClient
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse
from patrol.validation.scoring import MinerScore


@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.uuid")
async def test_challenge_sends_correct_synapse(mock_uuid):
    miner_client = AsyncMock(AlphaSellMinerClient)
    dashboard_client = AsyncMock(DashboardClient)

    axon_info = AxonInfo(0, "0.0.0.0", 0, 4, "hk", "ck")
    miner = Miner(axon_info, 123)
    batch_id = uuid.uuid4()

    task_id = uuid.uuid4()
    mock_uuid.uuid4.return_value = task_id

    batch = AlphaSellChallengeBatch(
        batch_id=batch_id, subnet_uid=42,
        prediction_interval=PredictionInterval(5_000_000, 5_000_7200),
        hotkeys_ss58=["alice", "bob"],
        created_at=datetime.now(UTC),
    )

    challenge = AlphaSellMinerChallenge(miner_client, dashboard_client)

    expected_synapse = AlphaSellSynapse(
        batch_id=str(batch_id), task_id=str(task_id), subnet_uid=42,
        prediction_interval=PredictionInterval(5_000_000, 5_000_7200),
        wallet_hotkeys_ss58=["alice", "bob"]
    )

    async for _ in challenge.execute_challenge(miner, [batch]):
        pass

    miner_client.execute_tasks.assert_awaited_once_with(axon_info, [expected_synapse])
    miner_client.execute_tasks.assert_awaited_once_with(axon_info, [expected_synapse])

    dashboard_client.send_score.assert_not_awaited()

@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.uuid")
async def test_challenge_sends_failed_score_to_dashboard(mock_uuid):
    miner_client = AsyncMock(AlphaSellMinerClient)
    dashboard_client = AsyncMock(DashboardClient)

    axon_info = AxonInfo(0, "0.0.0.0", 0, 4, "hk", "ck")
    miner = Miner(axon_info, 123)
    batch_id = uuid.uuid4()

    task_id = uuid.uuid4()
    mock_uuid.uuid4.return_value = task_id

    batch = AlphaSellChallengeBatch(
        batch_id=batch_id, subnet_uid=42,
        prediction_interval=PredictionInterval(5_000_000, 5_000_7200),
        hotkeys_ss58=["alice", "bob"],
        created_at=datetime.now(UTC),
    )

    miner_client.execute_tasks.return_value = [MinerTaskException("Nope!", task_id, batch_id)]

    challenge = AlphaSellMinerChallenge(miner_client, dashboard_client)

    async for _ in challenge.execute_challenge(miner, [batch]):
        pass

    dashboard_client.send_score.assert_awaited_once()
    score: MinerScore = dashboard_client.send_score.mock_calls[0][1][0]
    assert score.accuracy_score == 0
    assert not score.validation_passed
    assert "Nope!" in score.error_message
    assert score.task_type == TaskType.PREDICT_ALPHA_SELL


@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.datetime")
@patch("patrol.validation.predict_alpha_sell.alpha_sell_miner_challenge.uuid")
async def test_challenge_miner(mock_uuid, mock_datetime):

    now = datetime.now(UTC)
    task_id = uuid.uuid4()

    mock_datetime.now.return_value = now
    mock_uuid.uuid4.return_value = task_id

    batch_id = uuid.uuid4()
    subnet_uid = 42
    hotkeys = ["alice", "bob"]
    prediction_interval = PredictionInterval(5_000_000, 5_000_7200)
    predictions = [
        AlphaSellPrediction("alice", "alice_ck", TransactionType.STAKE_REMOVED, 25.0),
        AlphaSellPrediction("bob", "bob_ck", TransactionType.STAKE_REMOVED, 15.0),
    ]

    miner_client = AsyncMock(AlphaSellMinerClient)
    dashboard_client = AsyncMock(DashboardClient)

    miner_client.execute_tasks.return_value = [(batch_id, task_id, AlphaSellSynapse(
        batch_id=str(batch_id), task_id=str(task_id), subnet_uid=subnet_uid, prediction_interval=prediction_interval,
        wallet_hotkeys_ss58=hotkeys,
        predictions=predictions
    ))]

    axon = AxonInfo(version=0, ip="0.0.0.0", port=8000, hotkey="miner_hk", coldkey="miner_ck", ip_type=4)
    miner = Miner(axon, 123)

    batch = AlphaSellChallengeBatch(batch_id, now, subnet_uid, prediction_interval, hotkeys)

    challenge = AlphaSellMinerChallenge(miner_client, dashboard_client)
    tasks = [it async for it in challenge.execute_challenge(miner, [batch])]
    task = tasks[0]

    assert task.batch_id == batch_id
    assert task.created_at == now
    assert task.task_id == task_id
    assert task.predictions == predictions
    assert task.miner.uid == 123
    assert task.miner.hotkey == "miner_hk"
    assert task.miner.coldkey == "miner_ck"
