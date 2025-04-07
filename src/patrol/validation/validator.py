"""Functionality for asynchronously sending requests to a miner"""
import uuid
from typing import Callable

import uuid
import bittensor as bt
import patrol
from patrol.validation.persistence.miner_score_respository import DatabaseMinerScoreRepository
from patrol.validation.scoring import MinerScoreRepository
import asyncio
import aiohttp
import time
import logging
from uuid import UUID

from patrol.protocol import PatrolSynapse
from patrol.constants import Constants
from patrol.validation.target_generation import TargetGenerator
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.validation.graph_validation.bittensor_validation_mechanism import BittensorValidationMechanism
from patrol.validation.miner_scoring import MinerScoring
from patrol.validation.scoring import MinerScore

from bittensor.core.metagraph import AsyncMetagraph
import bittensor_wallet as btw
from patrol.validation.weight_setter import WeightSetter

logger = logging.getLogger(__name__)

class Validator:

    def __init__(self,
        validation_mechanism: BittensorValidationMechanism,
        target_generator: TargetGenerator,
        scoring_mechanism: MinerScoring,
        miner_score_repository: MinerScoreRepository,
        dendrite: bt.Dendrite,
        metagraph: AsyncMetagraph,
        uuid_generator: Callable[[], UUID],
        weight_setter: WeightSetter,
    ):
        self.validation_mechanism = validation_mechanism
        self.scoring_mechanism = scoring_mechanism
        self.target_generator = target_generator
        self.miner_score_repository = miner_score_repository
        self.dendrite = dendrite
        self.metagraph = metagraph
        self.uuid_generator = uuid_generator
        self.weight_setter = weight_setter

    async def query_miner(self,
        batch_id: UUID,
        uid: int,
        axon_info: bt.AxonInfo,
        target_tuple,
    ) -> MinerScore:

        synapse = PatrolSynapse(target=target_tuple[0], target_block_number=target_tuple[1])
        processed_synapse = self.dendrite.preprocess_synapse_for_request(axon_info, synapse)

        url = self.dendrite._get_endpoint_url(axon_info, "PatrolSynapse")

        trace_config = aiohttp.TraceConfig()
        timings = {}

        @trace_config.on_request_start.append
        async def on_request_start(sess, ctx, params):
            timings['request_start'] = time.perf_counter()

        @trace_config.on_response_chunk_received.append
        async def on_response_end(sess, ctx, params):
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

        validation_results = await self.validation_mechanism.validate_payload(uid, payload_subgraph, target=target_tuple[0])

        logger.debug(f"calculating coverage score for miner {uid}")
        miner_score = self.scoring_mechanism.calculate_score(uid, axon_info.coldkey, axon_info.hotkey, validation_results, response_time, batch_id)

        await self.miner_score_repository.add(miner_score)

        logger.info(f"Finished processing {uid}. Final Score: {miner_score.overall_score}. Response Time: {response_time}")
        return miner_score


    async def query_miner_batch(self):
        batch_id = self.uuid_generator()

        await self.metagraph.sync()
        axons = self.metagraph.axons
        uids = self.metagraph.uids.tolist()

        targets = await self.target_generator.generate_targets(len(uids))

        logger.info(f"Selected {len(targets)} targets for batch with id: {batch_id}.")

        tasks = []
        for i, axon in enumerate(axons):
            if axon.port != 0:
                target = targets.pop()
                tasks.append(self.query_miner(batch_id, uids[i], axon, target))

        await asyncio.gather(*tasks, return_exceptions=True)

        await self._set_weights(batch_id)


    async def _set_weights(self, batch_id: UUID):
        weights = await self.weight_setter.calculate_weights(batch_id)
        await self.weight_setter.set_weights(weights)


async def start():

    from patrol.validation.config import DB_URL, NETWORK, NET_UID, WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH

    wallet = btw.Wallet(WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH)
    engine = patrol.validation.config.db_engine
    subtensor = bt.async_subtensor(NETWORK)
    miner_score_repository = DatabaseMinerScoreRepository(engine)

    metagraph = await subtensor.metagraph(NET_UID)
    coldkey_finder = ColdkeyFinder(subtensor.substrate)
    mock_weight_setter = WeightSetter(miner_score_repository, subtensor, wallet, NET_UID)

    event_fetcher = EventFetcher()

    dendrite = bt.Dendrite(wallet)

    miner_validator = Validator(
        validation_mechanism=BittensorValidationMechanism(event_fetcher, coldkey_finder),
        target_generator=TargetGenerator(event_fetcher, coldkey_finder),
        scoring_mechanism=MinerScoring(),
        miner_score_repository=miner_score_repository,
        dendrite=dendrite,
        metagraph=metagraph,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=mock_weight_setter
    )

    while True:
        try:
            await miner_validator.query_miner_batch()
        except Exception as ex:
            logger.exception("Error!")
        await asyncio.sleep(10 * 60)

def boot():
    try:
        asyncio.run(start())
    except KeyboardInterrupt as ex:
        logger.info("Exiting")

if __name__ == "__main__":
   boot()

# async def test_miner():
#
#     bt.debug()
#
#     fetcher = EventFetcher()
#     await fetcher.initialize_substrate_connections()
#
#     scoring_mechanism = MinerScoring()
#
#     coldkey_finder = ColdkeyFinder()
#     await coldkey_finder.initialize_substrate_connection()
#
#     validator_mechanism = BittensorValidationMechanism(fetcher, coldkey_finder)
#     target_generator = TargetGenerator(fetcher, coldkey_finder)
#
#     targets = await target_generator.generate_targets(10)
#
#     target = ("5EPdHVcvKSMULhEdkfxtFohWrZbFQtFqwXherScM7B9F6DUD", 5163655)
#
#     wallet_2 = bt.wallet(name="miners", hotkey="miner_1")
#     dendrite = bt.dendrite(wallet=wallet_2)
#
#     wallet = bt.wallet(name="miners", hotkey="miner_1")
#     axon = bt.axon(wallet=wallet, ip="0.0.0.0", port=8000)
#
#     semaphore = asyncio.Semaphore(1)
#
#     await query_miner(1, dendrite, axon, target, "placehold_id", validator_mechanism, scoring_mechanism, semaphore)
