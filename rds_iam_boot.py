import logging
import os
from pathlib import Path

import boto3
from sqlalchemy import event, make_url
from patrol.validation import config, validator

logger = logging.getLogger(__name__)

@event.listens_for(config.db_engine.sync_engine, "do_connect")
def _on_connect(dialect, conn_rec, cargs, cparams):
    logger.info("Obtaining AWS RDS IAM password...")
    url = make_url(config.DB_URL)
    cparams["password"] = generate_auth_token(url)

def generate_auth_token(url):
    aws_region = os.getenv('AWS_REGION', "eu-west-2")
    rds_client = boto3.client("rds", region_name=aws_region)
    return rds_client.generate_db_auth_token(
        DBHostname=url.host,
        Port=url.port,
        DBUsername=url.username,
        Region=os.getenv('AWS_REGION', "eu-west-2")
    )

def fetch_wallet():
    s3 = boto3.client("s3")

    wallet_name = os.getenv('WALLET_NAME', "default")
    wallet_path = Path("~/.bittensor").expanduser() / "wallets" / wallet_name
    (wallet_path / "hotkeys").mkdir(parents=True)

    s3.download_file(
        Bucket=os.environ["WALLET_BUCKET"],
        Key=f"bittensor/{wallet_name}/coldkeypub.txt",
        Filename=str(wallet_path / "coldkeypub.txt")
    )
    hotkey_name = os.getenv('HOTKEY_NAME', "default")
    s3.download_file(
        Bucket=os.environ["WALLET_BUCKET"],
        Key=f"bittensor/{wallet_name}/hotkeys/{hotkey_name}",
        Filename=str(wallet_path / "hotkeys" / hotkey_name)
    )

if __name__ == "__main__":
    fetch_wallet()
    validator.boot()
