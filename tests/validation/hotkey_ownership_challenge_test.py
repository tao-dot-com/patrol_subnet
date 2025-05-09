from unittest.mock import AsyncMock

from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipChallenge
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient


def test():

    client = AsyncMock(HotkeyOwnershipMinerClient)


    #challenge = HotkeyOwnershipChallenge(client, chain_reader, scoring, validator, score_repository)