import asyncio
import logging
import re
import time

import httpx

from app.integrations.off import ProviderError

logger = logging.getLogger(__name__)

# The Food.com keyword actor (parseforge/food-com-scraper). It is pay-per-result, so
# every caller of ``search_recipes`` must bound both the item count and the wall clock.
RECIPE_ACTOR_PATH = "acts/L9lMlZe30ghx2Zdv3"
RECIPE_SORT = "PERFORMANCE"
TERMINAL_RUN_STATUSES = ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT")
POLL_INTERVAL_SECONDS = 2.0


def _optional_float(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


class ApifyReader:
    """Read completed runs/datasets, plus one bounded billable keyword search."""

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
            logger.warning(
                "Apify read failed path=%s status=%s type=%s",
                path,
                getattr(getattr(exc, "response", None), "status_code", None),
                type(exc).__name__,
            )
            raise ProviderError(
                "Apify data could not be read; check the existing dataset ID and access permissions."
            ) from exc

    async def _send(self, method: str, path: str, headers: dict, **kwargs):
        """One Apify v2 call returning the unwrapped ``data`` object.

        The token travels in a header (never a query string), and failures are
        logged by path and status only, so no secret reaches the log.
        """
        try:
            response = await self.client.request(
                method, "https://api.apify.com/v2/" + path, headers=headers, **kwargs
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Apify request failed method=%s path=%s status=%s type=%s",
                method,
                path,
                getattr(getattr(exc, "response", None), "status_code", None),
                type(exc).__name__,
            )
            raise ProviderError(
                "The recipe source could not be reached; try again in a moment."
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ProviderError("The recipe source returned an unexpected response.")
        return data

    async def search_recipes(
        self, query: str, max_items: int, timeout_seconds: int, token: str | None
    ) -> dict:
        """Start exactly one bounded Food.com keyword run and read its dataset.

        This is the only billable method here. The actor charges per returned
        result, so ``max_items`` caps the spend and ``timeout_seconds`` is passed
        to the run and also caps how long this coroutine waits for it. Returns
        ``{"items", "run_id", "dataset_id", "status", "cost_usd"}`` and raises
        :class:`ProviderError` with a plain message on any failure. ``cost_usd``
        is the run's reported ``usageTotalUsd`` (may be 0 while Apify settles).
        """
        headers = {"Authorization": f"Bearer {token}"} if token else dict(self.headers)
        if not headers:
            raise ProviderError("Live recipe search needs an Apify token.")
        run = await self._send(
            "POST",
            f"{RECIPE_ACTOR_PATH}/runs",
            headers,
            json={"searchQuery": query, "sortBy": RECIPE_SORT, "maxItems": max_items},
            params={"timeout": timeout_seconds},
        )
        run_id = run.get("id")
        if not isinstance(run_id, str) or not run_id:
            raise ProviderError("The recipe search did not return a run ID.")

        deadline = time.monotonic() + timeout_seconds
        status = run.get("status")
        while status not in TERMINAL_RUN_STATUSES:
            if time.monotonic() >= deadline:
                raise ProviderError(
                    "The recipe search did not finish in time; no recipes were imported."
                )
            await asyncio.sleep(min(POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic())))
            run = await self._send("GET", f"actor-runs/{run_id}", headers)
            status = run.get("status")
        if status != "SUCCEEDED":
            raise ProviderError(f"The recipe search ended as {status}; no recipes were imported.")
        dataset_id = run.get("defaultDatasetId")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ProviderError("The recipe search finished without a dataset.")
        items = await self.items(dataset_id, limit=max_items)
        return {
            "items": items if isinstance(items, list) else [],
            "run_id": run_id,
            "dataset_id": dataset_id,
            "status": status,
            "cost_usd": _optional_float(run.get("usageTotalUsd")),
        }

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
