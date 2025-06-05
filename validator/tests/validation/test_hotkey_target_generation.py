# tests/test_hotkey_target_generator.py

import pytest
import random
from unittest.mock import AsyncMock, MagicMock

import patrol.validation.hotkey_ownership.hotkey_target_generation as htg
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator

def test_format_address_success(monkeypatch):
    # simulate decode_account_id working
    monkeypatch.setattr(
        htg,
        "decode_account_id",
        lambda x: f"decoded_{x}"
    )
    out = HotkeyTargetGenerator.format_address("alice")
    assert out == "decoded_alice"


def test_format_address_failure(monkeypatch):
    # simulate decode_account_id raising
    def _boom(x):
        raise ValueError("nope")
    monkeypatch.setattr(htg, "decode_account_id", _boom)

    out = HotkeyTargetGenerator.format_address("raw_addr")
    assert out == "raw_addr"


@pytest.mark.asyncio
async def test_generate_random_block_numbers(monkeypatch):
    # force randint to always return 500
    monkeypatch.setattr(random, "randint", lambda a, b: 500)
    mock_client = MagicMock()
    mock_client.return_runtime_versions = AsyncMock(return_value=None)
    gen = HotkeyTargetGenerator(mock_client)

    # choose a current_block large enough so high >= low
    blocks = await gen.generate_random_block_numbers(num_blocks=2, current_block=5000)
    # num_blocks * 4 = 8 numbers, spaced by 500
    assert blocks == [500 + i * 500 for i in range(8)]


@pytest.mark.asyncio
async def test_fetch_subnets_and_owners(monkeypatch):
    # Setup a fake substrate_client.query
    # async def fake_query(method, *args, **kwargs):
    #     if method == "get_block_hash":
    #         return "fake_hash"
    #     elif method == "query_map":
    #         class Exists:
    #             def __init__(self, v): self.value = v
    #         async def gen():
    #             yield (1, Exists(True))
    #             yield (2, Exists(False))
    #             yield (3, Exists(True))
    #         return gen()
    #     elif method == "query":
    #         # args = (ver, module, name, [netuid])
    #         netuid = args[3][0]
    #         return f"owner{netuid}"
    #     else:
    #         raise RuntimeError(f"unexpected {method!r}")

    mock_client = MagicMock()
    #mock_client.query = AsyncMock(side_effect=fake_query)
    mock_client.get_block_hash = AsyncMock(return_value="fake_hash")

    async def mock_query_map(*args, **kwargs):
        class Exists:
            def __init__(self, v): self.value = v
        async def gen():
            yield (1, Exists(True))
            yield (2, Exists(False))
            yield (3, Exists(True))
        return gen()

    mock_client.query_map = AsyncMock(side_effect=mock_query_map)

    async def mock_query(*args, **kwargs):
        netuid = args[2][0]
        return f"owner{netuid}"

    mock_client.query = AsyncMock(side_effect=mock_query)

    # mock_client.return_runtime_versions = MagicMock(return_value={
    #     '261': {'block_number_min': 99, 'block_hash_min': 'test', 'block_number_max': 201, 'block_hash_max': 'test'}
    # })
    gen = HotkeyTargetGenerator(mock_client)

    subnets, owners = await gen.fetch_subnets_and_owners(block=100, current_block=200)
    # should pick only netuids 1 and 3
    assert subnets == [(100, 1), (100, 3)]
    assert owners == {"owner1", "owner3"}


@pytest.mark.asyncio
async def test_query_metagraph_direct(monkeypatch):
    # stub get_version_for_block
    # monkeypatch.setattr(
    #     htg,
    #     "get_version_for_block",
    #     lambda block, curr, rv: "VER"
    # )
    # async def fake_query(method, *args, **kwargs):
    #     if method == "get_block_hash":
    #         return "BH"
    #     elif method == "runtime_call":
    #         # return raw bytes
    #         return b"hello_neurons"
    #     else:
    #         raise RuntimeError()

    mock_client = MagicMock()
    # mock_client.query = AsyncMock(side_effect=fake_query)
    # mock_client.return_runtime_versions = AsyncMock(return_value=None)
    mock_client.get_block_hash = AsyncMock(return_value="BH")
    mock_client.runtime_call = AsyncMock(return_value=b"hello_neurons")

    gen = HotkeyTargetGenerator(mock_client)

    out = await gen.query_metagraph_direct(block_number=42, netuid=7, current_block=100)
    assert out == "hello_neurons"


@pytest.mark.asyncio
async def test_generate_targets(monkeypatch):
    # prepare generator
    mock_client = MagicMock()
    mock_client.return_runtime_versions = AsyncMock(return_value=None)
    gen = HotkeyTargetGenerator(mock_client)

    # 2) pick exactly two blocks
    monkeypatch.setattr(gen, "generate_random_block_numbers", AsyncMock(return_value=[100, 200]))
    # 3) fake fetch_subnets_and_owners
    async def fake_fetch(block, curr):
        if block == 100:
            return ([(100, 1), (100, 2)], {"o1"})
        else:
            return ([(200, 3)], {"o2", "o3"})
    monkeypatch.setattr(gen, "fetch_subnets_and_owners", fake_fetch)
    # 4) override random.sample so it won't error even if list < 5
    monkeypatch.setattr(random, "sample", lambda lst, n: lst)
    # 5) fake query_metagraph_direct to return two neurons each
    async def fake_qmd(block_number, netuid, current_block):
        return [
            {"hotkey": [f"hk{block_number}_{netuid}_A"]},
            {"hotkey": [f"hk{block_number}_{netuid}_B"]}
        ]
    monkeypatch.setattr(gen, "query_metagraph_direct", fake_qmd)
    # 6) identity format_address
    monkeypatch.setattr(
        HotkeyTargetGenerator,
        "format_address",
        staticmethod(lambda x: x[0])
    )
    # 7) no-op shuffle
    monkeypatch.setattr(random, "shuffle", lambda x: None)

    out = await gen.generate_targets(1000, num_targets=4)
    # we expect at most 4 unique items drawn from owners {o1,o2,o3}
    # plus hotkeys A/B for each of 3 subnets = 6 more -> total 9 possible
    assert isinstance(out, list)
    assert len(out) == 4
    allowed = {
        "o1", "o2", "o3",
        "hk100_1_A", "hk100_1_B", "hk100_2_A", "hk100_2_B",
        "hk200_3_A", "hk200_3_B"
    }
    for item in out:
        assert item in allowed