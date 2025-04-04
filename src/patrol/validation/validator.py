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
from patrol.validation.target_generation import TargetGenerator
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScore

async def query_miner(uid: int, 
                      dendrite: bt.dendrite, 
                      axon: bt.axon, 
                      target_tuple: str,
                      validation_mechanism: BittensorValidationMechanism,
                      scoring_mechanism: MinerScoring,
                      semaphore: asyncio.Semaphore) -> MinerScore:
    
    synapse = PatrolSynapse(target=target_tuple[0], target_block_number=target_tuple[1])

    axon_info = axon.info()

    processed_synapse = dendrite.preprocess_synapse_for_request(axon_info, synapse)

    url = dendrite._get_endpoint_url(axon, "PatrolSynapse")

    async with semaphore:

        async with aiohttp.ClientSession() as session:

            bt.logging.info(f"Requesting url: {url}")
            start_time = time.time() 
            try:
                    
                async with session.post(
                        url,
                        headers=processed_synapse.to_headers(),
                        json=processed_synapse.model_dump(),
                        timeout=Constants.MAX_RESPONSE_TIME
                    ) as response:
                        # Extract the JSON response from the server
                        json_response = await response.json()

                        response_time = time.time() - start_time

            except aiohttp.ClientConnectorError as e:
                bt.logging.error(f"Failed to connect to miner {uid}.  Skipping.")
                return
            except TimeoutError as e:
                bt.logging.error(f"Timeout error for miner {uid}.  Skipping.")
                return
            except Exception as e:
                bt.logging.error(f"Error for miner {uid}.  Skipping.  Error: {e}")
                return

    # Handling the post-processing
    try:
        payload_subgraph = json_response['subgraph_output']
    except KeyError:
        bt.logging.warning(f"Miner {uid} returned a non-standard response.  returned: {json_response}")
        payload_subgraph = None
        
    bt.logging.debug(f"Payload received for UID {uid}.")

    validation_results = await validation_mechanism.validate_payload(uid, payload_subgraph, target=target_tuple[0])

    bt.logging.debug(f"calculating coverage score for miner {uid}")
    miner_score = scoring_mechanism.calculate_score(uid, axon_info.coldkey, axon_info.hotkey, validation_results, response_time)

    bt.logging.info(f"Finished processing {uid}. Final Score: {miner_score.overall_score}. Response Time: {response_time}")

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

    bt.logging.info(f"Selected {len(targets)} targets.")

    semaphore = asyncio.Semaphore(1)

    tasks = []

    for i, axon in enumerate(axons):
            if axon.port != 0:
                target = targets.pop()
                tasks.append(query_miner(1, dendrite, axon, target, validator_mechanism, scoring_mechanism, semaphore), return_exceptions=True)

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

    await query_miner(1, dendrite, axon, target, validator_mechanism, scoring_mechanism, semaphore)

if __name__ == "__main__":
    
    asyncio.run(test_miner())
        

        

