import logging

from sqlalchemy.orm import DeclarativeBase
from alembic.config import Config
from pathlib import Path


logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass


def migrate_db(url: str):
    logging.info("Started DB migration")

    from alembic import command

    alembic_config = Config(Path(__file__).with_name("alembic.ini"))
    alembic_config.set_main_option('sqlalchemy.url', url)
    command.upgrade(alembic_config, 'head')

    logging.info("Completed DB migration")