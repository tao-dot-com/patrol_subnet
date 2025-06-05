from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncEngine

from patrol.validation import hooks
from patrol.validation.hooks import HookType


def test_invoke_on_start_hook():

    invoked = False
    def my_hook():
        nonlocal invoked
        invoked = True

    hooks.add_before_start_hook(my_hook)

    assert not invoked
    hooks.invoke(hook_type=HookType.BEFORE_START)

    assert invoked

def test_invoke_on_db_engine_hook():

    captured_engine = None
    def my_hook(engine: AsyncEngine):
        nonlocal captured_engine
        captured_engine = engine

    hooks.add_on_create_db_engine(my_hook)

    assert not captured_engine
    mock_engine = MagicMock(AsyncEngine)
    hooks.invoke(HookType.ON_CREATE_DB_ENGINE, mock_engine)

    assert captured_engine