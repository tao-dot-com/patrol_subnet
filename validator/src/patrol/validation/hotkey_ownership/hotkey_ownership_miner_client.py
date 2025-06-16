import time
import aiohttp
from bittensor import AxonInfo, Dendrite

from patrol.validation.error import MinerTaskException
from patrol_common.protocol import HotkeyOwnershipSynapse


class HotkeyOwnershipMinerClient:

    def __init__(self, dendrite: Dendrite, timeout_seconds: float=60.0):
        self._dendrite = dendrite
        self._timeout_seconds = timeout_seconds

    async def execute_task(self, miner: AxonInfo, synapse: HotkeyOwnershipSynapse) -> tuple[HotkeyOwnershipSynapse, float]:

        processed_synapse = self._dendrite.preprocess_synapse_for_request(miner, synapse)
        url = f"http://{miner.ip}:{miner.port}/{synapse.name}"
        headers = processed_synapse.to_headers()
        json_body = processed_synapse.model_dump()

        trace_config = aiohttp.TraceConfig()
        timings = {}

        @trace_config.on_request_chunk_sent.append
        async def on_request_start(sess, ctx, params):
            timings['request_start'] = time.perf_counter()

        @trace_config.on_response_chunk_received.append
        async def on_response_end(sess, ctx, params):
            if 'response_received' not in timings:
                timings['response_received'] = time.perf_counter()

        try:
            async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:
                response = await session.post(url, headers=headers, json=json_body, timeout=self._timeout_seconds, ssl=False)
                if not response.ok:
                    raise MinerTaskException(f"Error: {response.reason}; status {response.status}")
                response_synapse = HotkeyOwnershipSynapse.model_validate_json(await response.text())
                response_time = timings['response_received'] - timings['request_start']
                return response_synapse, response_time
        except TimeoutError:
            raise MinerTaskException("Timeout")
        except Exception as ex:
            raise MinerTaskException(str(ex))
