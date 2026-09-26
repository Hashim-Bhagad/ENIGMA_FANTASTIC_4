import logging

import httpx

from app.integrations.off import ProviderError

logger = logging.getLogger(__name__)


class FssaiVerifier:
    """Call TheVerifico's FSSAI license verification endpoint."""

    endpoint = "https://api.theverifico.com/api/v1/verify/fssai"

    def __init__(self, client: httpx.AsyncClient, api_key: str | None):
        self.client = client
        self.api_key = api_key

    async def verify(self, fssai_number: str) -> dict:
        if not self.api_key:
            raise ProviderError("FSSAI verification is not configured on this server.")
        try:
            response = await self.client.post(
                self.endpoint,
                headers={"X-API-Key": self.api_key},
                json={"fssai_number": fssai_number},
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Provider returned a non-object response")
            return result
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "TheVerifico FSSAI request failed status=%s type=%s",
                getattr(getattr(exc, "response", None), "status_code", None),
                type(exc).__name__,
            )
            raise ProviderError("FSSAI verification provider is unavailable; retry later.") from exc
