import os
from sqlalchemy.ext.asyncio import create_async_engine

NETWORK = os.getenv('NETWORK', "finney")
NET_UID = int(os.getenv('NET_UID', "81"))

DB_DIR = os.getenv('DB_DIR', "/var/patrol/sqlite")
DB_URL = os.getenv("DB_URL", f"sqlite+aiosqlite:///{DB_DIR}/patrol.db")

db_engine = create_async_engine(DB_URL)

WALLET_NAME = os.getenv('WALLET_NAME', "default")
HOTKEY_NAME = os.getenv('HOTKEY_NAME', "default")
BITTENSOR_PATH = os.getenv('BITTENSOR_PATH')

ENABLE_WEIGHT_SETTING = os.getenv('ENABLE_WEIGHT_SETTING', "1") == "1"
ARCHIVE_SUBTENSOR = os.getenv('ARCHIVE_SUBTENSOR', "wss://archive.chain.opentensor.ai:443")

SCORING_INTERVAL_SECONDS = int(os.getenv('SCORING_INTERVAL_SECONDS', "600"))