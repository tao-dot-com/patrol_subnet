import logging
from enum import Enum
from typing import Callable

from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

class HookType(Enum):
    BEFORE_START = "before-start"
    ON_CREATE_DB_ENGINE = "on-create-db-engine"

_hooks = {}

def add_before_start_hook(hook: Callable[[], None]):
    _hooks[HookType.BEFORE_START] = hook

def add_on_create_db_engine(hook: Callable[[AsyncEngine], None]):
    _hooks[HookType.ON_CREATE_DB_ENGINE] = hook

def invoke(hook_type: HookType, *args):
    if hook_type in _hooks:
        logger.info("Invoking %s hook", hook_type)
        _hooks[hook_type](*args)