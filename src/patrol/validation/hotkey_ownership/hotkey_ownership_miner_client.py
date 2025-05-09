import time
from typing import cast

from bittensor import AxonInfo, Dendrite

from patrol.protocol import HotkeyOwnershipSynapse

class MinerTaskException(Exception):
    pass


class HotkeyOwnershipMinerClient:

    def __init__(self, dendrite: Dendrite):
        self._dendrite = dendrite

    async def execute_task(self, miner: AxonInfo, synapse: HotkeyOwnershipSynapse) -> tuple[HotkeyOwnershipSynapse, float]:
        start_time = time.perf_counter()

        response = await self._dendrite.call(miner, synapse, timeout=60, deserialize=False)

        response_time = time.perf_counter() - start_time

        if response.is_failure:
            raise MinerTaskException(f"Error: {response.dendrite.status_message}; status {response.dendrite.status_code}")

        return cast(HotkeyOwnershipSynapse, response), response_time