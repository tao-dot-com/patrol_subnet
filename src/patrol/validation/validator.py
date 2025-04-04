"""Functionality for asynchronously sending requests to a miner"""

import bittensor as bt
from patrol.chain_data import event_fetcher
from patrol.validation.scoring import MinerScoreRepository
from substrateinterface import SubstrateInterface
from async_substrate_interface import AsyncSubstrateInterface
import asyncio
import aiohttp
import time

from patrol.protocol import PatrolSynapse
from patrol.constants import Constants
from patrol.validation.target_generation import TargetGenerator, generate_targets
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScore

logger = logging.getLogger(__name__)

async def query_miner(
    batch_id: UUID,
    uid: int,
    dendrite: bt.dendrite,
    axon: bt.axon,
    target_tuple,
    validation_mechanism: BittensorValidationMechanism,
    scoring_mechanism: MinerScoring,
    miner_score_repository: MinerScoreRepository
):
    synapse = PatrolSynapse(target=target_tuple[0], target_block_number=target_tuple[1])
    axon_info = axon.info()
    processed_synapse = dendrite.preprocess_synapse_for_request(axon_info, synapse)

    url = dendrite._get_endpoint_url(axon, "PatrolSynapse")

    trace_config = aiohttp.TraceConfig()
    timings = {}

    @trace_config.on_request_start.append
    async def on_request_start(session, ctx, params):
        timings['request_start'] = time.perf_counter()

    @trace_config.on_response_chunk_received.append
    async def on_response_end(session, ctx, params):
        timings['response_received'] = time.perf_counter()

    async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:

        logger.info(f"Requesting url: {url}")
        try:
            async with session.post(
                    url,
                    headers=processed_synapse.to_headers(),
                    json=processed_synapse.model_dump(),
                    timeout=Constants.MAX_RESPONSE_TIME
                ) as response:
                    # Extract the JSON response from the server
                    json_response = await response.json()
                    response_time = timings['response_received'] - timings["request_start"]

        except aiohttp.ClientConnectorError as e:
            logger.exception(f"Failed to connect to miner {uid}.  Skipping.")
        except TimeoutError as e:
            logger.error(f"Timeout error for miner {uid}.  Skipping.")
        except Exception as e:
            logger.error(f"Error for miner {uid}.  Skipping.  Error: {e}")

    # Handling the post-processing
    try:
        payload_subgraph = json_response['subgraph_output']
    except KeyError:
        logger.warning(f"Miner {uid} returned a non-standard response.  returned: {json_response}")
        payload_subgraph = None

    logger.debug(f"Payload received for UID {uid}.")

    validation_results = await validation_mechanism.validate_payload(uid, payload_subgraph, target=target_tuple[0])

    logger.debug(f"calculating coverage score for miner {uid}")
    miner_score = scoring_mechanism.calculate_score(uid, axon_info.coldkey, axon_info.hotkey, validation_results, response_time)

    await miner_score_repository.add(miner_score)

    logger.info(f"Finished processing {uid}. Final Score: {miner_score.overall_score}. Response Time: {response_time}")

# FIXME: Why does the dendrite/validator need a forward? Surely it should just run on a acheduled basis?
async def query_miners(metagraph: bt.metagraph,
                        dendrite: bt.dendrite,
                        my_uid: int,
                        target_generator: TargetGenerator,
                        validator_mechanism: BittensorValidationMechanism,
                        scoring_mechanism: MinerScoring,
                  ):

    start_time = time.time()
    axons = metagraph.axons

    targets = await target_generator.generate_targets(10)

    batch_id = str(uuid.uuid4())

    bt.logging.info(f"Selected {len(targets)} targets for batch with id: {batch_id}.")

    semaphore = asyncio.Semaphore(1)

    tasks = []

    for i, axon in enumerate(axons):
            if axon.port != 0:
                target = targets.pop()
                tasks.append(query_miner(1, dendrite, axon, target, batch_id, validator_mechanism, scoring_mechanism, semaphore), return_exceptions=True)

    responses = await asyncio.gather(*tasks)
    
    # We want to run this every 10 minutes, so calculate the sleep time. 
    # Get the difference between the current time and 10 minutes since the start time.
    sleep_time = 10 * 60 - (time.time() - start_time)

    if sleep_time > 0:
        time.sleep(sleep_time)


async def test_miner():

    bt.debug()

    fetcher = EventFetcher()
    await fetcher.initialize_substrate_connections()
    
    scoring_mechanism = MinerScoring()

    coldkey_finder = ColdkeyFinder()
    await coldkey_finder.initialize_substrate_connection()

    validator_mechanism = BittensorValidationMechanism(fetcher, coldkey_finder)
    target_generator = TargetGenerator(fetcher, coldkey_finder)

    targets = await target_generator.generate_targets(10)

    target = ("5EPdHVcvKSMULhEdkfxtFohWrZbFQtFqwXherScM7B9F6DUD", 5163655)

    wallet_2 = bt.wallet(name="miners", hotkey="miner_1")
    dendrite = bt.dendrite(wallet=wallet_2)

    wallet = bt.wallet(name="miners", hotkey="miner_1")
    axon = bt.axon(wallet=wallet, ip="0.0.0.0", port=8000)

    semaphore = asyncio.Semaphore(1)

    await query_miner(1, dendrite, axon, target, "placehold_id", validator_mechanism, scoring_mechanism, semaphore)

if __name__ == "__main__":
    
    asyncio.run(test_miner())
        

        

