"""Synchronous HTTP client for the Maintainer's Copilot API.

All functions return a dict. On success the dict contains the response payload.
On failure the dict contains {"error": "<human-readable message>"}.
Tokens and secrets are never printed or logged.
"""

from __future__ import annotations

import httpx

from chatbot.config import API_BASE_URL, MODEL_SERVER_URL, REQUEST_TIMEOUT


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(email: str, password: str) -> dict:
    url = f"{API_BASE_URL}/api/v1/auth/login"
    try:
        r = httpx.post(
            url,
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API. Is the server running?"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def me(token: str) -> dict:
    url = f"{API_BASE_URL}/api/v1/auth/me"
    try:
        r = httpx.get(url, headers=_auth_headers(token), timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def chat(
    message: str,
    *,
    conversation_id: str | None = None,
    user_id: str | None = None,
    token: str | None = None,
    enabled_tools: list[str] | None = None,
) -> dict:
    url = f"{API_BASE_URL}/api/v1/chat"
    headers = _auth_headers(token) if token else {}
    payload: dict = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if user_id:
        payload["user_id"] = user_id
    if enabled_tools is not None:
        payload["enabled_tools"] = enabled_tools
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API. Is the server running?"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def rag_query(
    question: str,
    *,
    top_k: int = 5,
    retriever: str = "hybrid",
    query_transform: str = "none",
    source_type: str | None = None,
    maintainer_only: bool = False,
    token: str | None = None,
) -> dict:
    url = f"{API_BASE_URL}/api/v1/rag/query"
    payload: dict = {
        "question": question,
        "top_k": top_k,
        "retriever": retriever,
        "query_transform": query_transform,
        "maintainer_only": maintainer_only,
    }
    if source_type:
        payload["source_type"] = source_type
    headers = _auth_headers(token) if token else {}
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def check_api_health() -> dict:
    url = f"{API_BASE_URL}/healthz"
    try:
        r = httpx.get(url, timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "status": r.json().get("status", "ok")}
        return {"ok": False, "status": f"HTTP {r.status_code}"}
    except httpx.ConnectError:
        return {"ok": False, "status": "unreachable"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": type(exc).__name__}


def check_model_server_health() -> dict:
    url = f"{MODEL_SERVER_URL}/healthz"
    try:
        r = httpx.get(url, timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "status": "ok"}
        return {"ok": False, "status": f"HTTP {r.status_code}"}
    except httpx.ConnectError:
        return {"ok": False, "status": "unreachable"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": type(exc).__name__}


def get_short_term_memory(conversation_id: str, token: str) -> dict:
    url = f"{API_BASE_URL}/api/v1/memory/short-term"
    try:
        r = httpx.get(
            url,
            params={"conversation_id": conversation_id},
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def get_long_term_memories(
    token: str,
    *,
    conversation_id: str | None = None,
) -> dict:
    url = f"{API_BASE_URL}/api/v1/memory/long-term"
    params: dict = {}
    if conversation_id:
        params["conversation_id"] = conversation_id
    try:
        r = httpx.get(
            url,
            params=params,
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def list_widgets(token: str) -> dict:
    url = f"{API_BASE_URL}/api/v1/admin/widgets"
    try:
        r = httpx.get(url, headers=_auth_headers(token), timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return {"items": r.json()}
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}


def create_widget(
    token: str,
    *,
    allowed_origins: list[str],
    greeting: str = "Hi! How can I help?",
    enabled_tools: list[str] | None = None,
    theme: dict | None = None,
    is_active: bool = True,
) -> dict:
    url = f"{API_BASE_URL}/api/v1/admin/widgets"
    payload: dict = {
        "allowed_origins": allowed_origins,
        "greeting": greeting,
        "is_active": is_active,
    }
    if enabled_tools is not None:
        payload["enabled_tools"] = enabled_tools
    if theme is not None:
        payload["theme"] = theme
    try:
        r = httpx.post(
            url, json=payload, headers=_auth_headers(token), timeout=REQUEST_TIMEOUT
        )
        if r.status_code == 201:
            return r.json()
        detail = r.json().get("detail", f"HTTP {r.status_code}")
        return {"error": detail}
    except httpx.ConnectError:
        return {"error": "Cannot connect to API."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {type(exc).__name__}"}
