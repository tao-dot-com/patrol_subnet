import os
from typing import Optional

import numpy as np
from bittensor import AxonInfo
from bittensor.core.metagraph import AsyncMetagraph

from patrol.validation import TaskType

NETWORK = os.getenv('NETWORK', "finney")
NET_UID = int(os.getenv('NET_UID', "81"))

DB_URL = os.getenv("DB_URL", f"postgresql+asyncpg://patrol:password@localhost:5432/patrol")

WALLET_NAME = os.getenv('WALLET_NAME', "default")
HOTKEY_NAME = os.getenv('HOTKEY_NAME', "default")
BITTENSOR_PATH = os.getenv('BITTENSOR_PATH')

ENABLE_WEIGHT_SETTING = os.getenv('ENABLE_WEIGHT_SETTING', "1") == "1"
ARCHIVE_SUBTENSOR = os.getenv('ARCHIVE_SUBTENSOR', "wss://archive.chain.opentensor.ai:443")

SCORING_INTERVAL_SECONDS = int(os.getenv('SCORING_INTERVAL_SECONDS', "60"))
WEIGHT_SETTING_INTERVAL_SECONDS = int(os.getenv('WEIGHT_SETTING_INTERVAL_SECONDS', "60"))

ENABLE_AUTO_UPDATE = os.getenv('ENABLE_AUTO_UPDATE', "0") == "1"

MAX_RESPONSE_SIZE_BYTES = 1024 * 1024 * int(os.getenv('MAX_RESPONSE_SIZE_MB', "64"))
BATCH_CONCURRENCY = int(os.getenv('BATCH_CONCURRENCY', "8"))

DASHBOARD_BASE_URL = os.getenv('DASHBOARD_BASE_URL', "https://patrol.tao.com")
ENABLE_DASHBOARD_SYNDICATION = os.getenv('ENABLE_DASHBOARD_SYNDICATION', "1") == "1"

#COLDKEY_SEARCH_TASK_WEIGHT = int(os.getenv('PATROL_TASK_WEIGHT', 80))
HOTKEY_OWNERSHIP_TASK_WEIGHT = int(os.getenv('HOTKEY_OWNERSHIP_TASK_WEIGHT', 60))
PREDICT_ALPHA_SELL_TASK_WEIGHT = int(os.getenv('PREDICT_ALPHA_SELL_TASK_WEIGHT', 40))

TASK_WEIGHTS: dict[TaskType, int] = {
    #TaskType.COLDKEY_SEARCH: COLDKEY_SEARCH_TASK_WEIGHT,
    TaskType.HOTKEY_OWNERSHIP: HOTKEY_OWNERSHIP_TASK_WEIGHT,
    TaskType.PREDICT_ALPHA_SELL: PREDICT_ALPHA_SELL_TASK_WEIGHT
}


class StaticAsyncMetagraph(AsyncMetagraph):

    def __init__(self, axons: list[AxonInfo]):
        super().__init__(netuid=81, sync=False)
        self.axons = axons
        self.uids = np.array(list(range(4, 4 + len(axons))))

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def sync(
        self,
        block: Optional[int] = None,
        lite: Optional[bool] = None,
        subtensor = None,
    ):
        pass


def patrol_metagraph():
    json_mg = os.getenv('PATROL_AXONS_JSON')
    if json_mg is None:
        return None

    import json
    mg = json.loads(json_mg)
    axons = [AxonInfo(**it) for it in mg]
    return StaticAsyncMetagraph(axons)

PATROL_METAGRAPH: AsyncMetagraph | None = patrol_metagraph()

ENABLE_ALPHA_SELL_TASK = bool(os.getenv('ENABLE_ALPHA_SELL_TASK', "1") == "1")
ENABLE_HOTKEY_OWNERSHIP_TASK = bool(os.getenv('ENABLE_HOTKEY_OWNERSHIP_TASK', "1") == "1")

ALPHA_SELL_PREDICTION_WINDOW_BLOCKS = int(os.getenv('ALPHA_SELL_PREDICTION_WINDOW_BLOCKS', "7200"))
ALPHA_SELL_TASK_INTERVAL_SECONDS = int(os.getenv('ALPHA_SELL_TASK_INTERVAL_SECONDS', "1800"))