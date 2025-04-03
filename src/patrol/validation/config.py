import os
from sqlalchemy.ext.asyncio import create_async_pool_from_url

DB_DIR = os.getenv('DB_DIR', "/tmp/sqlite")
DB_URL = os.getenv("DB_URL", f"sqlite+aiosqlite:///{DB_DIR}/patrol.db")

db_engine = create_async_pool_from_url(DB_URL)
