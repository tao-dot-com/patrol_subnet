"""Functionality for asynchronously sending requests to a miner"""

import bittensor as bt
from patrol.validation.scoring import MinerScoreRepository
from substrateinterface import SubstrateInterface
from async_substrate_interface import AsyncSubstrateInterface
import asyncio
import aiohttp
import time
import logging

from patrol.protocol import PatrolSynapse
from patrol.constants import Constants
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def query_miner(uid: int, 
                      dendrite: bt.dendrite, 
                      axon: bt.axon, 
                      target: str, 
                      target_block_number: int,
                      semaphore: asyncio.Semaphore):
    
    synapse = PatrolSynapse(target=target, target_block_number=target_block_number)

    processed_synapse = dendrite.preprocess_synapse_for_request(axon, synapse)

    url = dendrite._get_endpoint_url(axon, "PatrolSynapse")

    async with semaphore:

        async with aiohttp.ClientSession() as session:

            logger.info(f"Requesting url: {url}")
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
                logger.error(f"Failed to connect to miner {uid}.  Skipping.")
                return
            except TimeoutError as e:
                logger.error(f"Timeout error for miner {uid}.  Skipping.")
                return
            except Exception as e:
                logger.error(f"Error for miner {uid}.  Skipping.  Error: {e}")
                return

    # Handling the post-processing
    try:
        payload_subgraph = json_response['subgraph_output']
    except KeyError:
        logger.warning(f"Miner {uid} returned a non-standard response.  returned: {json_response}")
        payload_subgraph = None

    if payload_subgraph is None:
        logger.warning(f"Payload subgraph is None for UID {uid}. Skipping coverage score calculation.")
        miner_scoring = 0
    else:
        
        logger.debug(f"Payload received for UID {uid} with {len(payload_subgraph.nodes)} nodes and {len(payload_subgraph.edges)} edges.")

        validation_mechanism = BittensorValidationMechanism() #Validation mechanism for Bittensor payloads (more datasource types coming soon)

        # logger.debug(f"validating payload for miner {uid}")
        validation_results = await validation_mechanism.validate_payload(uid, payload_subgraph, target=target)

        # Calculate the Coverage score for the miner
        logger.debug(f"calculating coverage score for miner {uid}")
        miner_scoring = MinerScoring()
        coverage_score = miner_scoring.calculate_score(payload_subgraph, validation_results, response_time)

    # miner_scoring.cache_scores(uid, coverage_score)
    logger.info(f"Finished processing {uid}. Final Score: {coverage_score}. Response Time: {response_time}")


# FIXME: Why does the dendrite/validator need a forward? Surely it should just run on a acheduled basis?
# TODO: Why not just use a scheduled job at a fixed interval instead of an infinite loop???
async def forward(metagraph: bt.metagraph, 
                        dendrite: bt.dendrite, 
                        config: bt.config, 
                        my_uid: int,
                        wallet: bt.wallet,
                        miner_score_repository: MinerScoreRepository
                  ):

    weight_watcher = WeightWatcher(config, my_uid, wallet)
    while True:
        start_time = time.time()

        # FIXME: you want to sync the metagraph in case sopme more miners have appeared since th last time we ran.
        axons = metagraph.axons

        target_selector = TargetSelector() 
        targets, target_block_number= target_selector.select_targets(n=len(axons)) 

        logger.info(f"Selected {len(targets)} targets for block {target_block_number}")

        semaphore = asyncio.Semaphore(1)

        tasks = []

        for i, axon in enumerate(axons):
                if axon.port != 0:
                    target = targets.pop()
                    tasks.append(query_miner(i, dendrite, axon, target, target_block_number, semaphore))

        responses = await asyncio.gather(*tasks)

        if weight_watcher.should_set_weights():
            weight_watcher.set_weights()
        
        # We want to run this every 10 minutes, so calculate the sleep time. 
        # Get the difference between the current time and 10 minutes since the start time.
        sleep_time = 10 * 60 - (time.time() - start_time)

        if sleep_time > 0:
            # FIXME: This will block the event loop! Use the asycio equivalent.
            time.sleep(sleep_time)


# async def test_miner():

#     target_selector = TargetSelector() 
#     targets, target_block_number= target_selector.select_targets(n=1) 

#     target = targets.pop()

#     wallet_2 = bt.wallet(name="miners", hotkey="miner_1")
#     dendrite = bt.dendrite(wallet=wallet_2)

#     wallet = bt.wallet(name="miners", hotkey="miner_1")
#     axon = bt.axon(wallet=wallet, ip="0.0.0.0", port=8000)

#     semaphore = asyncio.Semaphore(1)

#     await query_miner(1, dendrite, axon, target, target_block_number, semaphore)

# if __name__ == "__main__":
    
#     asyncio.run(test_miner())
        

        

