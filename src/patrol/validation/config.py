import os

from patrol.constants import TaskType

NETWORK = os.getenv('NETWORK', "finney")
NET_UID = int(os.getenv('NET_UID', "81"))

DB_DIR = os.getenv('DB_DIR', "/var/patrol/sqlite")
DB_URL = os.getenv("DB_URL", f"sqlite+aiosqlite:///{DB_DIR}/patrol.db")

WALLET_NAME = os.getenv('WALLET_NAME', "default")
HOTKEY_NAME = os.getenv('HOTKEY_NAME', "default")
BITTENSOR_PATH = os.getenv('BITTENSOR_PATH')

ENABLE_WEIGHT_SETTING = os.getenv('ENABLE_WEIGHT_SETTING', "1") == "1"
ARCHIVE_SUBTENSOR = os.getenv('ARCHIVE_SUBTENSOR', "wss://archive.chain.opentensor.ai:443")

SCORING_INTERVAL_SECONDS = int(os.getenv('SCORING_INTERVAL_SECONDS', "60"))
ENABLE_AUTO_UPDATE = os.getenv('ENABLE_AUTO_UPDATE', "0") == "1"

MAX_RESPONSE_SIZE_BYTES = 1024 * 1024 * int(os.getenv('MAX_RESPONSE_SIZE_MB', "64"))
BATCH_CONCURRENCY = int(os.getenv('BATCH_CONCURRENCY', "8"))

DASHBOARD_BASE_URL = os.getenv('DASHBOARD_BASE_URL', "https://patrol.tao.com")
ENABLE_DASHBOARD_SYNDICATION = os.getenv('ENABLE_DASHBOARD_SYNDICATION', "1") == "1"

COLDKEY_SEARCH_TASK_WEIGHT = int(os.getenv('PATROL_TASK_WEIGHT', 80))
HOTKEY_OWNERSHIP_TASK_WEIGHT = int(os.getenv('HOTKEY_OWNERSHIP_TASK_WEIGHT', 20))

TASK_WEIGHTS: dict[TaskType, int] = {
    TaskType.COLDKEY_SEARCH: COLDKEY_SEARCH_TASK_WEIGHT,
    TaskType.HOTKEY_OWNERSHIP: HOTKEY_OWNERSHIP_TASK_WEIGHT,
}
