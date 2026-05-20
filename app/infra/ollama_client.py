"""Async HTTP client for the Ollama local API.

Usage (from a service):
    client = OllamaClient()
    content = await client.chat(model="llama3:latest", messages=[...])

Config values are module-level constants so they can be overridden by env or
passed explicitly — never hardcoded inside calling functions.
"""

from __future__ import annotations

import httpx

from app.domain.errors import OllamaUnavailableError

DEFAULT_BASE_URL: str = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS: float = 120.0
DEFAULT_MODEL: str = "llama3:latest"
DEFAULT_TEMPERATURE: float = 0.0


class OllamaClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(
        self,
        model: str,
        messages: list[dict],
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        """Send a /api/chat request and return the assistant message content.

        Raises OllamaUnavailableError on connection failure, timeout, or bad response.
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["message"]["content"]
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(
                f"Ollama not reachable at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise OllamaUnavailableError(
                f"Ollama timed out after {self._timeout}s"
            ) from exc
        except (httpx.HTTPStatusError, KeyError) as exc:
            raise OllamaUnavailableError(f"Ollama response error: {exc}") from exc
