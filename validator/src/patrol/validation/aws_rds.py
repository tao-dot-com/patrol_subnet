import logging
import os

import boto3
from sqlalchemy import event, make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from patrol.validation import config

logger = logging.getLogger(__name__)

def consume_db_engine(engine: AsyncEngine):
    logger.info("Applying DB event listener")
    @event.listens_for(engine.sync_engine, "do_connect")
    def _on_connect(dialect, conn_rec, cargs, cparams):
        url = make_url(config.DB_URL)
        cparams["password"] = generate_auth_token(url)

def generate_auth_token(url):
    logger.info("Obtaining AWS RDS IAM password...")
    aws_region = os.getenv('AWS_REGION', "eu-west-2")
    rds_client = boto3.client("rds", region_name=aws_region)
    return rds_client.generate_db_auth_token(
        DBHostname=url.host,
        Port=url.port,
        DBUsername=url.username,
        Region=aws_region
    )
