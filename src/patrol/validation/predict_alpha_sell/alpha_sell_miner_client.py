import asyncio
from uuid import UUID

import aiohttp
from bittensor import AxonInfo, Dendrite

from patrol.validation.error import MinerTaskException
from patrol.validation.predict_alpha_sell.protocol import AlphaSellSynapse


class AlphaSellMinerClient:
    def __init__(self, dendrite: Dendrite, timeout_seconds: float=60.0):
        self._dendrite = dendrite
        self._timeout_seconds = timeout_seconds

    async def execute_tasks(self, miner: AxonInfo, synapses: list[AlphaSellSynapse]) -> list[tuple[UUID, UUID, AlphaSellSynapse]]:

        async with aiohttp.ClientSession(base_url=f"http://{miner.ip}:{miner.port}") as session:
            tasks = [self._execute_task(session, miner, synapse) for synapse in synapses]
            return await asyncio.gather(*tasks, return_exceptions=True)


    async def _execute_task(self, session, miner: AxonInfo, synapse: AlphaSellSynapse) -> tuple[UUID, UUID, AlphaSellSynapse]:
        processed_synapse = self._dendrite.preprocess_synapse_for_request(miner, synapse)

        uri = f"/{synapse.name}"
        headers = processed_synapse.to_headers()
        json_body = processed_synapse.model_dump()

        try:
            response = await session.post(uri, headers=headers, json=json_body, timeout=self._timeout_seconds, ssl=False)
            if not response.ok:
                raise MinerTaskException(f"Error: {response.reason}; status {response.status}")
            response_synapse = AlphaSellSynapse.model_validate_json(await response.text())
            return UUID(synapse.batch_id), UUID(synapse.task_id), response_synapse
        except TimeoutError:
            raise MinerTaskException("Timeout")
        except Exception as ex:
            raise MinerTaskException(str(ex))
