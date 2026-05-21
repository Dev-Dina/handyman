"""HTTP client for the model server (E5 embeddings, CodeBERT classification).

Usage (from a service):
    client = ModelServerClient()
    embeddings = await client.embed(["query: how does pod scheduling work?"], model="intfloat/e5-small-v2")
"""

from __future__ import annotations

import httpx

from app.domain.errors import ModelServerUnavailableError

DEFAULT_MODELSERVER_URL: str = "http://modelserver:8001"
DEFAULT_TIMEOUT_SECONDS: float = 30.0


class ModelServerClient:
    def __init__(
        self,
        base_url: str = DEFAULT_MODELSERVER_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        """Request dense embeddings from the model server.

        Returns one float vector per input text.
        Raises ModelServerUnavailableError on connection failure or bad response.
        """
        payload = {"texts": texts, "model": model}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/embed", json=payload)
                resp.raise_for_status()
                return resp.json()["embeddings"]
        except httpx.ConnectError as exc:
            raise ModelServerUnavailableError(
                f"Model server not reachable at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ModelServerUnavailableError(
                f"Model server timed out after {self._timeout}s"
            ) from exc
        except (httpx.HTTPStatusError, KeyError) as exc:
            raise ModelServerUnavailableError(f"Model server error: {exc}") from exc
