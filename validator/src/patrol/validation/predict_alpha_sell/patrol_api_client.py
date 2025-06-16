
import asyncio
import aiohttp
from patrol.validation.http_.security import JwtGenerator
from patrol.validation.predict_alpha_sell import AlphaSellChallengeTask, AlphaSellChallengeRepository


class PatrolApiClient:
    def __init__(self, endpoint_url: str, token_generator: JwtGenerator):
        self.endpoint_url = endpoint_url
        self.token_generator = token_generator

    async def send(self, tasks: list[AlphaSellChallengeTask]):

        async with aiohttp.ClientSession(base_url=self.endpoint_url) as session:
            response = await session.post(url="/foo", headers = {
                "Authorization": f"Bearer {self.token_generator.get_token()}",
            })
            response.raise_for_status()


class PredictionSyndicator:
    def __init__(self,
         patrol_api_client: PatrolApiClient,
         challenge_repository: AlphaSellChallengeRepository,
         interval_seconds: int = 300
    ):
        self.patrol_api_client = patrol_api_client
        self.challenge_repository = challenge_repository
        self.interval_seconds = interval_seconds

    async def syndicate_predictions(self):
        predictions = await self.challenge_repository.find_predictions()
        for chunk in predictions:
            await self.patrol_api_client.send(chunk)
            task_ids = [chunk.task_id for chunk in chunk]
            await self.challenge_repository.mark_tasks_syndicated(task_ids)


    async def start(self):
        async def background_job():
            while True:
                await self.syndicate_predictions()
                await asyncio.sleep(self.interval_seconds)

        asyncio.create_task(background_job())



