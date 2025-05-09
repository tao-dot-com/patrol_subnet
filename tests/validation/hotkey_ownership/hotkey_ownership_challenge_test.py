from datetime import datetime, UTC
import uuid
from unittest.mock import AsyncMock, patch

from bittensor import AxonInfo

from patrol.protocol import HotkeyOwnershipSynapse, GraphPayload, Node, Edge, HotkeyOwnershipEvidence
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge, \
    HotkeyOwnershipValidator, Miner
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring, HotkeyOwnershipScore
from patrol.validation.scoring import MinerScoreRepository, MinerScore

@patch("patrol.validation.hotkey_ownership.hotkey_ownership_challenge.datetime")
async def test_execute_and_score_challenge(mock_datetime):

    now = datetime.now(UTC)
    mock_datetime.now.return_value = now

    client = AsyncMock(HotkeyOwnershipMinerClient)
    scoring = AsyncMock(HotkeyOwnershipScoring)
    validator = AsyncMock(HotkeyOwnershipValidator)
    score_repository = AsyncMock(MinerScoreRepository)

    client.execute_task.return_value = (HotkeyOwnershipSynapse(
        target_hotkey_ss58="target",
        subgraph_output=GraphPayload(
            nodes=[Node("alice", "", ""), Node("bob", "", "")],
            edges=[
                Edge(
                    coldkey_source="alice", coldkey_destination="bob",
                    category="", type="",
                    evidence=HotkeyOwnershipEvidence(123)
                )
            ]
        )), 2.0)

    challenge = HotkeyOwnershipChallenge(client, scoring, validator, score_repository)

    miner = Miner(
        axon_info=AxonInfo(
            ip="127.0.0.1", port=8000,
            hotkey="alice", coldkey="bob",
            ip_type=4, version=0
        ),
        uid=12
    )

    batch_id = uuid.uuid4()
    scoring.score.return_value=HotkeyOwnershipScore(1, 0.5, 0.75)
    score_repository.find_latest_overall_scores.return_value=[0, 1, 2]

    task_id = await challenge.execute_challenge(miner, "fsdgfdsghfgdshgfh", batch_id)

    score_persisted: MinerScore = score_repository.add.mock_calls[0].args[0]
    assert score_persisted.overall_score == 0.75
    assert score_persisted.volume_score == 1
    assert score_persisted.novelty_score == 0
    assert score_persisted.responsiveness_score == 0.5
    assert score_persisted.volume == 0
    assert score_persisted.response_time_seconds == 2.0
    assert score_persisted.overall_score_moving_average == (0 + 1 + 2 + 0.75) / 20
    assert score_persisted.batch_id == batch_id
    assert score_persisted.uid == 12
    assert score_persisted.hotkey == "alice"
    assert score_persisted.coldkey == "bob"
    assert score_persisted.id == task_id
    assert score_persisted.created_at == now
