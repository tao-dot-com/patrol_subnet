import multiprocessing
from multiprocessing.synchronize import Semaphore

import bittensor as bt
from sqlalchemy.ext.asyncio import create_async_engine

from patrol.validation import auto_update, hooks
from patrol.validation.hooks import HookType
from patrol.validation.persistence import migrate_db
from patrol.validation.persistence.miner_score_repository import DatabaseMinerScoreRepository
import asyncio
import logging

import bittensor_wallet as btw
from patrol.validation.weight_setter import WeightSetter

logger = logging.getLogger(__name__)

class ResponsePayloadTooLarge(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class Validator:

    def __init__(self, weight_setter: WeightSetter):
        self.weight_setter = weight_setter

    async def set_weights(self):
        if await self.weight_setter.is_weight_setting_due():
            logger.info("Setting weights")
            weights = await self.weight_setter.calculate_weights()
            await self.weight_setter.set_weights(weights)
        else:
            logger.info("Weight setting is not due yet")

async def start(semaphore: Semaphore):

    from patrol.validation.config import (NETWORK, NET_UID, WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH,
                                          ENABLE_WEIGHT_SETTING, WEIGHT_SETTING_INTERVAL_SECONDS,
                                          ENABLE_AUTO_UPDATE, DB_URL,
                                          TASK_WEIGHTS)

    logger.info("Auto update is enabled" if ENABLE_AUTO_UPDATE else "Auto update is disabled")

    if ENABLE_WEIGHT_SETTING:
        logger.info("Weight setting is enabled.")
    else:
        logger.warning("Weight setting is not enabled.")

    wallet = btw.Wallet(WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH)
    logger.info(f"Wallet initialized: {WALLET_NAME}/{HOTKEY_NAME}")

    engine = create_async_engine(DB_URL, pool_pre_ping=True)
    hooks.invoke(HookType.ON_CREATE_DB_ENGINE, engine)

    subtensor = bt.async_subtensor(NETWORK)
    logger.info(f"Obtained subtensor for network ${NETWORK}")
    miner_score_repository = DatabaseMinerScoreRepository(engine)

    weight_setter = WeightSetter(miner_score_repository, subtensor, wallet, NET_UID, TASK_WEIGHTS)
    validator = Validator(weight_setter)
    logger.info(f"Validator initialized.")

    update_available = False
    loop = asyncio.get_running_loop()
    while not update_available:
        logger.info("Processing updates & weights - waiting for semaphore...")
        await loop.run_in_executor(None, semaphore.acquire)
        try:
            logger.info("Processing updates & weights.")
            update_available = ENABLE_AUTO_UPDATE and await auto_update.is_update_available()
            if update_available:
                logger.info("Update available - service will restart")
                break

            if ENABLE_WEIGHT_SETTING:
                logger.info("Weight setting is enabled. Checking due time...")
                await validator.set_weights()
        except Exception as ex:
            logger.exception("Error!")
        finally:
            await loop.run_in_executor(None, semaphore.release)
            await asyncio.sleep(WEIGHT_SETTING_INTERVAL_SECONDS)

def boot():
    try:
        hooks.invoke(HookType.BEFORE_START)

        from patrol.validation.config import DB_URL, ENABLE_DASHBOARD_SYNDICATION, WALLET_NAME, HOTKEY_NAME, \
            BITTENSOR_PATH, ENABLE_ALPHA_SELL_TASK, ENABLE_HOTKEY_OWNERSHIP_TASK, PATROL_METAGRAPH
        migrate_db(DB_URL)

        wallet = btw.Wallet(WALLET_NAME, HOTKEY_NAME, BITTENSOR_PATH)

        mp_ctx = multiprocessing.get_context('fork')
        semaphore = Semaphore(ctx=mp_ctx)

        if ENABLE_ALPHA_SELL_TASK:
            logger.info("Starting ALPHA_SELL_TASK.")
            from patrol.validation.predict_alpha_sell import stake_event_collector, alpha_sell_miner_challenge, alpha_sell_scoring
            stake_event_collector.start_process(DB_URL)
            alpha_sell_miner_challenge.start_process(wallet, db_url=DB_URL, enable_dashboard_syndication=ENABLE_DASHBOARD_SYNDICATION,
                                                     patrol_metagraph=PATROL_METAGRAPH)
            alpha_sell_scoring.start_scoring_process(wallet, DB_URL, semaphore, ENABLE_DASHBOARD_SYNDICATION)

        if ENABLE_HOTKEY_OWNERSHIP_TASK:
            logger.info("Starting HOTKEY_OWNERSHIP_TASK.")
            from patrol.validation.hotkey_ownership import hotkey_ownership_batch
            hotkey_ownership_batch.start_process(wallet, db_url=DB_URL, enable_dashboard_syndication=ENABLE_DASHBOARD_SYNDICATION,
                                                 patrol_metagraph=PATROL_METAGRAPH)
        logger.info("Starting main validator.")
        asyncio.run(start(semaphore))
        logger.info("Service Terminated.")

    except KeyboardInterrupt as ex:
        logger.info("Exiting")

if __name__ == "__main__":
    boot()