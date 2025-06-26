import asyncio
import logging
from importlib.metadata import version
from aiochclient.http_clients import aiohttp
from aiohttp import ClientSession

logger = logging.getLogger(__name__)

async def get_digest(session: ClientSession, tag: str, token: str) -> str | None :
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.docker.distribution.manifest.v2+json"
    }

    latest_manifest_res = await session.get(
        url=f"https://public.ecr.aws/v2/c9f7n4n0/patrol%2Fvalidator/manifests/{tag}",
        headers=headers
    )
    if latest_manifest_res.ok:
        response = await latest_manifest_res.json()
        if "manifests" in response:
            digest = response['manifests'][0]['digest']
            return digest
        elif "config" in response:
            return response['config']['digest']
        else:
            return None
    else:
        return None


async def is_update_available():
    logger.info("Checking for update...")

    async with aiohttp.ClientSession() as session:
        auth_res = await session.get(
            url="https://public.ecr.aws/token",
            params={"scope": f"repository:c9f7n4n0/patrol/validator:pull"}
        )
        token = (await auth_res.json())['token']

        package_version = version("patrol-validator")
        docker_tag = package_version.replace("+", "_")

        logger.info(f"Fetching digest for tag  %s",docker_tag)
        current_digest = await get_digest(session, docker_tag, token)
        logger.info("Current digest for tag %s: %s", docker_tag, current_digest)

        latest_digest = await get_digest(session, "latest", token)
        logger.info("Latest digest: %s", latest_digest)

    if current_digest is None or latest_digest is None:
        logger.warning("Failed to fetch digests; assuming latest.")
        return False
    elif current_digest == latest_digest:
        logger.info("Current version is latest.")
        return False
    else:
        logger.info("New version available: %s. Service will terminate.", latest_digest)
        return True

if __name__ == "__main__":
    import sys
    logging.basicConfig(level="INFO", stream=sys.stdout)
    new_version_available = asyncio.run(is_update_available())
    print(new_version_available)