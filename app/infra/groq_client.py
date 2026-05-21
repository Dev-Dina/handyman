"""Async HTTP client for the Groq OpenAI-compatible chat completions API.

Usage (from a service):
    client = GroqClient(api_key="gsk_...")
    choice = await client.chat(messages=[...], tools=[...])
    content = choice["message"]["content"]
    tool_calls = choice["message"].get("tool_calls") or []
"""

from __future__ import annotations

import httpx

from app.domain.errors import GroqUnavailableError

GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
FALLBACK_MODEL: str = "openai/gpt-oss-20b"
DEFAULT_TIMEOUT_SECONDS: float = 60.0
DEFAULT_TEMPERATURE: float = 0.0


class GroqClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = GROQ_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str = PRIMARY_MODEL,
        tools: list[dict] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> dict:
        """Send a chat completions request and return the first choice dict.

        The returned dict has the shape:
            {"message": {"role": "assistant", "content": ..., "tool_calls": [...]}}

        Raises GroqUnavailableError on connection failure, timeout, or API error.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]
        except httpx.ConnectError as exc:
            raise GroqUnavailableError(
                f"Groq not reachable at {self._base_url}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise GroqUnavailableError(
                f"Groq timed out after {self._timeout}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise GroqUnavailableError(
                f"Groq HTTP error {exc.response.status_code}"
            ) from exc
        except (KeyError, IndexError) as exc:
            raise GroqUnavailableError(
                f"Groq unexpected response shape: {exc}"
            ) from exc
