import dataclasses
import json
import random
from typing import Callable, Tuple, Any

import uuid
import bittensor as bt
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.chain_data.event_collector import EventCollector
from patrol.chain_data.event_processor import EventProcessor
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.validation import auto_update, hooks
from patrol.validation.graph_validation.event_checker import EventChecker
from patrol.validation.dashboard import DashboardClient
from patrol.validation.hooks import HookType
from patrol.validation.http.HttpDashboardClient import HttpDashboardClient
from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository
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
from patrol.chain_data.missed_block_retry_task import MissedBlocksRetryTask
from patrol.validation.persistence.missed_blocks_repository import MissedBlocksRepository

from bittensor.core.metagraph import AsyncMetagraph
import bittensor_wallet as btw
from patrol.validation.weight_setter import WeightSetter

logger = logging.getLogger(__name__)

class ResponsePayloadTooLarge(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Validator:

    def __init__(self,
        validation_mechanism: BittensorValidationMechanism,
        target_generator: TargetGenerator,
        scoring_mechanism: MinerScoring,
        miner_score_repository: MinerScoreRepository,
        dashboard_client: DashboardClient,
        dendrite: bt.Dendrite,
        metagraph: AsyncMetagraph,
        uuid_generator: Callable[[], UUID],
        weight_setter: WeightSetter,
        enable_weight_setting: bool,
        enable_dashboard_syndication: bool,
        concurrency: int = 10,
        max_response_size_bytes = 64E9,
    ):
        self.validation_mechanism = validation_mechanism
        self.scoring_mechanism = scoring_mechanism
        self.target_generator = target_generator
        self.miner_score_repository = miner_score_repository
        self.dashboard_client = dashboard_client
        self.dendrite = dendrite
        self.metagraph = metagraph
        self.uuid_generator = uuid_generator
        self.weight_setter = weight_setter
        self.miner_timing_semaphore = asyncio.Semaphore(concurrency)
        self.enable_weight_setting = enable_weight_setting
        self.concurrency = concurrency
        self.max_response_size_bytes = max_response_size_bytes
        self.enable_dashboard_syndication = enable_dashboard_syndication

    async def query_miner(self,
        batch_id: UUID,
        uid: int,
        axon_info: bt.AxonInfo,
        target_tuple: Tuple,
        max_block_number: int
    ) -> MinerScore:
    
        try:
            async with self.miner_timing_semaphore:
                synapse = PatrolSynapse(target=target_tuple[0], target_block_number=target_tuple[1], max_block_number=max_block_number)
                processed_synapse = self.dendrite.preprocess_synapse_for_request(axon_info, synapse)
                url = self.dendrite._get_endpoint_url(axon_info, "PatrolSynapse")
                json_response, response_time = await self._invoke_miner(url, processed_synapse)

                payload_subgraph = json_response['subgraph_output']
                logger.info(f"Payload received for UID %s in %s seconds.", uid, response_time)

                validation_result = await self.validation_mechanism.validate_payload(uid, payload_subgraph, target=target_tuple[0], max_block_number=max_block_number)
                logger.info(f"Calculating score for miner %s", uid)
                miner_score = await self.scoring_mechanism.calculate_score(
                    uid, axon_info.coldkey, axon_info.hotkey, validation_result, response_time, batch_id
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
            elif isinstance(ex, ResponsePayloadTooLarge):
                logger.info(f"Payload to large for miner {uid}. Skipping.")
                error_message = ex.message
            else:
                logger.info(f"Error for miner {uid}.  Skipping.  Error: {ex}")
                error_message = "Unknown error"

            miner_score = await self.scoring_mechanism.calculate_zero_score(
                batch_id, uid, axon_info.coldkey, axon_info.hotkey, error_message
            )

        await self.miner_score_repository.add(miner_score)
        if self.enable_dashboard_syndication:
            try:
                await self.dashboard_client.send_score(miner_score)
                logger.info("Sent scores to dashboard", extra=dataclasses.asdict(miner_score))
            except Exception as ex:
                logger.exception("Failed to send scores to dashboard", extra=dataclasses.asdict(miner_score))

        logger.info(f"Finished processing {uid}. Final Score: {miner_score.overall_score}")

        return miner_score

    async def _invoke_miner(self, url, processed_synapse) -> tuple[dict[str, Any], float]:
        trace_config = aiohttp.TraceConfig()
        timings = {}

        @trace_config.on_request_chunk_sent.append
        async def on_request_start(sess, ctx, params):
            timings['request_start'] = time.perf_counter()

        @trace_config.on_response_chunk_received.append
        async def on_response_end(sess, ctx, params):
            if 'response_received' not in timings:
                timings['response_received'] = time.perf_counter()

        async with aiohttp.ClientSession(trace_configs=[trace_config]) as session:

            logger.info(f"Requesting url: {url}")
            async with session.post(
                    url,
                    headers=processed_synapse.to_headers(),
                    json=processed_synapse.model_dump(),
                    timeout=Constants.MAX_RESPONSE_TIME
            ) as response:
                buffer = bytearray()
                if response.ok:
                    async for chunk in response.content.iter_chunked(8*1024):
                        buffer.extend(chunk)
                        if len(buffer) > self.max_response_size_bytes:
                            raise ResponsePayloadTooLarge(f"Response payload too large: Aborted at {len(buffer)} bytes")
                else:
                    raise Exception("Bad response status %s", response.status)

                response_time = time.perf_counter() - timings["request_start"]
                json_response = json.loads(buffer.decode('utf-8'))

                return json_response, response_time


    async def query_miner_batch(self):
        batch_id = self.uuid_generator()

        await self.metagraph.sync()

        if self.enable_weight_setting and await self.weight_setter.is_weight_setting_due():
            await self._set_weights()

        axons = self.metagraph.axons
        uids = self.metagraph.uids.tolist()

        targets = await self.target_generator.generate_targets(len(uids))
        current_block = await self.target_generator.get_current_block()
        max_block = current_block - 10 # provide a small buffer

        logger.info(f"Selected {len(targets)} targets for batch with id: {batch_id}.")

        triples = list(zip(uids, axons, targets))
        random.shuffle(triples) 
        
        current_block = await self.target_generator.get_current_block()
        max_block = current_block - 10 # provide a small buffer

        logger.info(f"Selected {len(targets)} targets for batch with id: {batch_id}.")

        tasks = [
            self.query_miner(batch_id, uid, axon, target, max_block)
            for uid, axon, target in triples if axon.port!=0
        ]


        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"Batch %s finished", batch_id)


    async def _set_weights(self):
        weights = await self.weight_setter.calculate_weights()
        await self.weight_setter.set_weights(weights)


async def sync_event_store(collector: EventCollector, block_retry_task: MissedBlocksRetryTask):
    # Start the event collector
    await collector.start()
    logger.info("Started Event Collector task in background")

    await block_retry_task.start()
    logger.info("Started Missed Block Retry task in background")
    
    check_interval_minutes = 10
    max_acceptable_block_gap = 10
    
    # Periodically check if we have enough blockchain data
    while True:
        # Get current block directly from the event fetcher
        current_block = await collector.event_fetcher.get_current_block()

        # Get highest block from collector's in-memory state instead of a database query
        highest_block = collector.last_synced_block

        # Still need to query db once, since collector won't have last synced block initially
        if highest_block is None:
            highest_block = await collector.event_repository.get_highest_block_from_db()
        
        if highest_block is None:
            block_gap = float('inf')  # No blocks in DB yet
        else:
            block_gap = current_block - highest_block
        
        logger.info(f"Database sync status: highest_block={highest_block}, current_block={current_block}, gap={block_gap} blocks")
        
        # If we're synced up enough, break out of the loop
        if block_gap <= max_acceptable_block_gap:
            logger.info(f"Database is sufficiently synced (gap: {block_gap} blocks). Proceeding with validation.")
            break
        
        logger.info(f"Waiting {check_interval_minutes} more minutes for database to sync (current gap: {block_gap} blocks)")
        await asyncio.sleep(check_interval_minutes * 60)  # Wait for the specified interval


async def start():

    from patrol.validation.config import (NETWORK, NET_UID, WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH,
                                          ENABLE_WEIGHT_SETTING, ARCHIVE_SUBTENSOR, SCORING_INTERVAL_SECONDS,
                                          ENABLE_AUTO_UPDATE, DB_URL, MAX_RESPONSE_SIZE_BYTES, BATCH_CONCURRENCY,
                                          DASHBOARD_BASE_URL, ENABLE_DASHBOARD_SYNDICATION)

    if ENABLE_AUTO_UPDATE:
        logger.info("Auto update is enabled")
    else:
        logger.warning("Auto update is disabled")

    if not ENABLE_WEIGHT_SETTING:
        logger.warning("Weight setting is not enabled.")

    wallet = btw.Wallet(WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH)

    engine = create_async_engine(DB_URL, pool_pre_ping=True)
    hooks.invoke(HookType.ON_CREATE_DB_ENGINE, engine)

    subtensor = bt.async_subtensor(NETWORK)
    miner_score_repository = DatabaseMinerScoreRepository(engine)

    versions = load_versions()

    my_substrate_client = SubstrateClient(versions, ARCHIVE_SUBTENSOR)
    await my_substrate_client.initialize()

    coldkey_finder = ColdkeyFinder(my_substrate_client)
    weight_setter = WeightSetter(miner_score_repository, subtensor, wallet, NET_UID)

    event_fetcher = EventFetcher(my_substrate_client)
    event_processor = EventProcessor(coldkey_finder)
    event_checker = EventChecker(engine)

    event_repository = DatabaseEventStoreRepository(engine)
    missed_blocks_repository = MissedBlocksRepository(engine)
    
    event_collector = EventCollector(
        event_fetcher=event_fetcher,
        event_processor=event_processor,
        event_repository=event_repository,
        missed_blocks_repository=missed_blocks_repository,
        sync_interval=12  # Default block time in seconds
    )
    missed_blocks_retry_task = MissedBlocksRetryTask(
        event_fetcher=event_fetcher,
        event_processor=event_processor,
        event_repository=event_repository,
        missed_blocks_repository=missed_blocks_repository,
        retry_interval_seconds=300 # Retry every 5 minutes
    )

    await sync_event_store(event_collector, missed_blocks_retry_task)

    dendrite = bt.Dendrite(wallet)

    metagraph = await subtensor.metagraph(NET_UID)
    miner_validator = Validator(
        validation_mechanism=BittensorValidationMechanism(event_checker),
        target_generator=TargetGenerator(event_fetcher, event_processor),
        scoring_mechanism=MinerScoring(miner_score_repository, moving_average_denominator=20),
        miner_score_repository=miner_score_repository,
        dashboard_client=HttpDashboardClient(wallet, DASHBOARD_BASE_URL),
        dendrite=dendrite,
        metagraph=metagraph,
        uuid_generator=lambda: uuid.uuid4(),
        weight_setter=weight_setter,
        enable_weight_setting=ENABLE_WEIGHT_SETTING,
        enable_dashboard_syndication=ENABLE_DASHBOARD_SYNDICATION,
        max_response_size_bytes=MAX_RESPONSE_SIZE_BYTES,
        concurrency=BATCH_CONCURRENCY
    )

    #await asyncio.wait_for(miner_validator.query_miner_batch(), timeout=60*60)
    
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
        hooks.invoke(HookType.BEFORE_START)

        from patrol.validation.config import DB_URL
        migrate_db(DB_URL)
        asyncio.run(start())
        logger.info("Service Terminated.")
    except KeyboardInterrupt as ex:
        logger.info("Exiting")

if __name__ == "__main__":
    boot()