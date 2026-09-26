import re

import httpx

from app.integrations.off import ProviderError


class ApifyReader:
    """Read completed runs/datasets only. Never starts a billable scraper run."""

    def __init__(self, client: httpx.AsyncClient, token: str | None = None):
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    async def get(self, path: str, **params):
        try:
            response = await self.client.get(
                "https://api.apify.com/v2/" + path, params=params, headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "Apify data could not be read; check the existing dataset ID and access permissions."
            ) from exc

    @staticmethod
    def validate_id(value: str):
        if not re.fullmatch(r"[A-Za-z0-9]{10,30}", value):
            raise ValueError("Expected an Apify run or dataset ID")

    async def run_dataset(self, run_id: str) -> str:
        self.validate_id(run_id)
        run = (await self.get(f"actor-runs/{run_id}"))["data"]
        if run["status"] != "SUCCEEDED":
            raise ProviderError("Only completed successful runs can be imported")
        return run["defaultDatasetId"]

    async def items(self, dataset_id: str, limit: int = 100, offset: int = 0):
        self.validate_id(dataset_id)
        return await self.get(
            f"datasets/{dataset_id}/items", format="json", clean="true", limit=limit, offset=offset
        )
