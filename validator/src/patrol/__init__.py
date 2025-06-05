import logging
from datetime import datetime, timezone
from logging import config
from pathlib import Path

from pythonjsonlogger.json import JsonFormatter

class PatrolJsonFormatter(JsonFormatter):
    def formatTime(self, record, datefmt = None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat(timespec="milliseconds")

import bittensor as bt
bt.logging.enable_third_party_loggers()
config.fileConfig(str(Path(__file__).with_name("logging.ini")))

from importlib.metadata import version
logging.info("Patrol Subnet. Version %s", version("patrol-subnet"))