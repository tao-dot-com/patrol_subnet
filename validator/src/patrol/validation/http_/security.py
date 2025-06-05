from datetime import datetime, UTC, timedelta

from aiochclient.http_clients import aiohttp


class JwtGenerator:
    def __init__(self, client_id, client_secret, endpoint: str = "https://patrol-api.auth.eu-west-2.amazoncognito.com"):
        self.base_url = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.expiry = None

    async def get_token(self):
        if self.expiry is not None and datetime.now(UTC) < self.expiry:
            return self.token

        async with aiohttp.ClientSession(base_url=self.base_url) as session:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            response = await session.post("/oauth2/token", data=data)
            response.raise_for_status()
            payload = await response.json()

            self.token = payload["access_token"]
            self.expiry = datetime.now(UTC) + timedelta(seconds=payload["expires_in"] - 60)

        return self.token
