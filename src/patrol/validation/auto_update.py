import asyncio
import logging
from importlib.metadata import version
import docker
from aiochclient.http_clients import aiohttp


logger = logging.getLogger(__name__)

CONTAINER_TAG = "postgres:16-alpine"

async def check_for_update():
    logger.info("Checking for update...")

    package_version = version("patrol-subnet")
    git_tag = package_version.replace("+", "_")

    docker_client = docker.from_env()
    containers = docker_client.containers.list(filters={"ancestor": "postgres:16-alpine"})
    container = containers[0] if len(containers) > 0 else None

    if not container:
        logger.warning(f"{CONTAINER_TAG} is not running. Auto update aborted.")
        return False

    if container:
        current_digest = container.image.id
        logger.info(f"Current digest: %s",current_digest)

        async with aiohttp.ClientSession() as session:
            auth_res = await session.get(
                url="https://public.ecr.aws/token",
                params={"scope": f"repository:c9f7n4n0/patrol/validator:pull"}
            )
            token = (await auth_res.json())['token']

            manifest_url = f"https://public.ecr.aws/v2/c9f7n4n0/patrol%2fvalidator/manifests/latest"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.docker.distribution.manifest.v2+json"
            }

            manifest_res = await session.get(manifest_url, headers=headers)
            digest = (await manifest_res.json())['config']['digest']

        logger.info("New version available: %s. Service will terminate.", digest)
        return digest != current_digest

if __name__ == "__main__":
    new_version_available = asyncio.run(check_for_update())
    print(new_version_available)