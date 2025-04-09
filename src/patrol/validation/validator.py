from typing import Callable, Tuple, Any

import uuid
import bittensor as bt
from aiohttp import TCPConnector

import patrol
from patrol.chain_data.event_processor import EventProcessor
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.validation import auto_update
from patrol.validation.persistence import migrate_db
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
        enable_weight_setting: bool,
    ):
        self.validation_mechanism = validation_mechanism
        self.scoring_mechanism = scoring_mechanism
        self.target_generator = target_generator
        self.miner_score_repository = miner_score_repository
        self.dendrite = dendrite
        self.metagraph = metagraph
        self.uuid_generator = uuid_generator
        self.weight_setter = weight_setter
        self.miner_timing_semaphore = asyncio.Semaphore(1)
        self.enable_weight_setting = enable_weight_setting
        self.conn = TCPConnector(limit_per_host=20)

    async def query_miner(self,
        batch_id: UUID,
        uid: int,
        axon_info: bt.AxonInfo,
        target_tuple: Tuple
    ) -> MinerScore:

        try:
            #async with self.miner_timing_semaphore:
            synapse = PatrolSynapse(target=target_tuple[0], target_block_number=target_tuple[1])
            processed_synapse = self.dendrite.preprocess_synapse_for_request(axon_info, synapse)
            url = self.dendrite._get_endpoint_url(axon_info, "PatrolSynapse")
            json_response, response_time = await self._invoke_miner(url, processed_synapse)

            payload_subgraph = json_response['subgraph_output']
            logger.info(f"Payload received for UID % in %s seconds.", uid, response_time)

            validation_results = await self.validation_mechanism.validate_payload(uid, payload_subgraph, target=target_tuple[0])
            logger.info(f"calculating coverage score for miner %s", uid)
            miner_score = await self.scoring_mechanism.calculate_score(
                uid, axon_info.coldkey, axon_info.hotkey, validation_results, response_time, batch_id
            )
        except Exception as ex:
            if isinstance(ex, aiohttp.ClientConnectorError):
                logger.info(f"Failed to connect to miner UID %s; assigning zero score.", uid)
                error_message = "Miner unresponsive"
            elif isinstance(ex, KeyError):
                logger.info(f"Miner UID %s returned a non-standard response: %s", uid, json_response)
                error_message = "Invalid response"
            elif isinstance(ex, TimeoutError):
                logger.info(f"Timeout error for miner {uid}. Skipping.")
                error_message = "Timeout"
            else:
                logger.info(f"Error for miner {uid}.  Skipping.  Error: {ex}")
                error_message = "Unknown error"

            miner_score = await self.scoring_mechanism.calculate_zero_score(
                batch_id, uid, axon_info.coldkey, axon_info.hotkey, error_message
            )

        await self.miner_score_repository.add(miner_score)

        logger.info(f"Finished processing {uid}. Final Score: {miner_score.overall_score}. Response Time: {response_time}")
        return miner_score

    async def _invoke_miner(self, url, processed_synapse) -> tuple[dict[str, Any], float]:
        trace_config = aiohttp.TraceConfig()
        timings = {}

        @trace_config.on_request_start.append
        async def on_request_start(sess, ctx, params):
            timings['request_start'] = time.perf_counter()

        @trace_config.on_response_chunk_received.append
        async def on_response_end(sess, ctx, params):
            timings['response_received'] = time.perf_counter()

        async with aiohttp.ClientSession(connector=self.conn, trace_configs=[trace_config]) as session:

            logger.info(f"Requesting url: {url}")
            async with session.post(
                    url,
                    headers=processed_synapse.to_headers(),
                    json=processed_synapse.model_dump(),
                    timeout=Constants.MAX_RESPONSE_TIME
            ) as response:
                json_response = await response.json()
                response_time = timings['response_received'] - timings["request_start"]

                return json_response, response_time


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

        if self.enable_weight_setting and await self.weight_setter.is_weight_setting_due():
            await self._set_weights()


    async def _set_weights(self):
        weights = await self.weight_setter.calculate_weights()
        await self.weight_setter.set_weights(weights)


async def start():

    from patrol.validation.config import (NETWORK, NET_UID, WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH,
                                          ENABLE_WEIGHT_SETTING, ARCHIVE_SUBTENSOR, SCORING_INTERVAL_SECONDS, ENABLE_AUTO_UPDATE)

    if ENABLE_AUTO_UPDATE:
        logger.info("Auto update is enabled")
    else:
        logger.warning("Auto update is disabled")

    if not ENABLE_WEIGHT_SETTING:
        logger.warning("Weight setting is not enabled.")

    wallet = btw.Wallet(WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH)
    engine = patrol.validation.config.db_engine
    subtensor = bt.async_subtensor(NETWORK)
    miner_score_repository = DatabaseMinerScoreRepository(engine)

    versions = load_versions()

    my_substrate_client = SubstrateClient(versions, ARCHIVE_SUBTENSOR)
    await my_substrate_client.initialize()

    coldkey_finder = ColdkeyFinder(my_substrate_client)
    weight_setter = WeightSetter(miner_score_repository, subtensor, wallet, NET_UID)

    event_fetcher = EventFetcher(my_substrate_client)
    event_processor = EventProcessor(coldkey_finder)

    dendrite = bt.Dendrite(wallet)

    metagraph = await subtensor.metagraph(NET_UID)
    miner_validator = Validator(
        validation_mechanism=BittensorValidationMechanism(event_fetcher, event_processor),
        target_generator=TargetGenerator(event_fetcher, event_processor),
        scoring_mechanism=MinerScoring(miner_score_repository),
        miner_score_repository=miner_score_repository,
        dendrite=dendrite,
        metagraph=metagraph,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=weight_setter,
        enable_weight_setting=ENABLE_WEIGHT_SETTING
    )


    update_available = False
    while not update_available:
        try:
            update_available = ENABLE_AUTO_UPDATE and await auto_update.is_update_available()
            if update_available:
                break
            await miner_validator.query_miner_batch()

        except Exception as ex:
            logger.exception("Error!")

        await asyncio.sleep(SCORING_INTERVAL_SECONDS)

def boot():
    try:
        from patrol.validation.config import DB_URL
        migrate_db(DB_URL)
        asyncio.run(start())
        logger.info("Service Terminated.")
    except KeyboardInterrupt as ex:
        logger.info("Exiting")

if __name__ == "__main__":
    boot()