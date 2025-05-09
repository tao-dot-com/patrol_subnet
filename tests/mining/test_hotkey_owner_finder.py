# tests/test_hotkey_owner_finder.py
import pytest
import asyncio
from unittest.mock import AsyncMock

from patrol.chain_data.runtime_groupings import VersionData
from patrol.constants import Constants
from patrol.mining.hotkey_owner_finder import HotkeyOwnerFinder
from patrol.protocol import Node, Edge, GraphPayload, HotkeyOwnershipEvidence


@pytest.fixture
def substrate_client():
    client = AsyncMock()
    async def fake_query(method, *args, **kwargs):
        if method == "get_block":
            return {"header": {"number": 123}}
        return "stub"
    client.query.side_effect = fake_query
    client.return_runtime_versions = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_get_current_block(substrate_client):
    finder = HotkeyOwnerFinder(substrate_client)
    blk = await finder.get_current_block()
    assert blk == 123
    substrate_client.query.assert_called_once_with("get_block", None)


@pytest.mark.asyncio
async def test__get_block_metadata(monkeypatch, substrate_client):
    # Replace get_version_for_block
    monkeypatch.setattr(
        "patrol.mining.hotkey_owner_finder.get_version_for_block",
        lambda block, curr, rv: "v42"
    )
    finder = HotkeyOwnerFinder(substrate_client)

    result = await finder._get_block_metadata(block_number=10, current_block=100)

    assert result == (10, "stub", "v42")
    # verify substrate_client called correctly
    substrate_client.query.assert_called_once_with("get_block_hash", None, 10)


@pytest.mark.asyncio
async def test_get_owner_at_with_and_without_current_block(monkeypatch, substrate_client):
    # Stub get_version_for_block via monkeypatch
    monkeypatch.setattr(
        "patrol.mining.hotkey_owner_finder.get_version_for_block",
        lambda block, curr, rv: "v1"
    )
    finder = HotkeyOwnerFinder(substrate_client)

    # --- Case A: current_block explicitly passed
    substrate_client.query.side_effect = [
        "0xhash",       # get_block_hash
        "OWNER_ADDR"    # query(...)
    ]
    owner = await finder.get_owner_at("hk", block_number=5, current_block=50)
    assert owner == "OWNER_ADDR"
    substrate_client.query.assert_any_call("get_block_hash", None, 5)
    substrate_client.query.assert_any_call(
        "query", "v1", "SubtensorModule", "Owner", ["hk"], block_hash="0xhash"
    )

    # --- Case B: current_block omitted → uses get_current_block()
    substrate_client.query.reset_mock()
    finder.get_current_block = AsyncMock(return_value=77)
    substrate_client.query.side_effect = [
        "0xhash2",      # get_block_hash
        "OTHER_OWNER"   # query(...)
    ]
    owner2 = await finder.get_owner_at("hk2", block_number=8)
    assert owner2 == "OTHER_OWNER"
    finder.get_current_block.assert_awaited_once()


@pytest.mark.asyncio
async def test__find_change_block_binary_search():
    # owner = "A" up to 10, then "B" → change at 11
    client = AsyncMock()
    client.return_runtime_versions = AsyncMock(return_value=None)
    finder = HotkeyOwnerFinder(client)

    async def fake_get_owner(hk, blk, curr):
        return "A" if blk <= 10 else "B"
    finder.get_owner_at = fake_get_owner

    change = await finder._find_change_block(
        "hk",
        low=0,
        high=20,
        owner_low="A",
        current_block=20
    )
    assert change == 11



@pytest.mark.asyncio
async def test_find_owner_ranges(monkeypatch):
    """
    Simulate two ownership spans:
      blocks [1..2] => owner X
      blocks [3..5] => owner Y
    """
    client = AsyncMock()
    client.return_runtime_versions = AsyncMock(return_value=None)
    finder = HotkeyOwnerFinder(client)

    # Force head to block 5
    finder.get_current_block = AsyncMock(return_value=5)

    # Stub get_owner_at: <3 -> X, else Y
    async def fake_owner(hk, blk, curr):
        return "X" if blk < 3 else "Y"
    finder.get_owner_at = fake_owner

    # Stub binary search: always returns change at 3
    finder._find_change_block = AsyncMock(return_value=3)

    payload: GraphPayload = await finder.find_owner_ranges("hotkey123", minimum_block=1)

    # Expect two wallet nodes: X then Y
    assert payload.nodes == [
        Node(id="X", type="wallet", origin="bittensor"),
        Node(id="Y", type="wallet", origin="bittensor")
    ]

    # Expect a single edge capturing the swap at block 3
    expected_edge = Edge(
        coldkey_source="X",
        coldkey_destination="Y",
        category="coldkey_swap",
        type="hotkey_ownership",
        evidence=HotkeyOwnershipEvidence(effective_block_number=3),
        coldkey_owner="Y"
    )
    assert payload.edges == [expected_edge]
