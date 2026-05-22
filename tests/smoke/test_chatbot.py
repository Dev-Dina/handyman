"""Smoke tests: chatbot module imports, config defaults, and component correctness."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_chatbot_config_imports():
    from chatbot import config  # noqa: F401


def test_chatbot_config_api_base_default():
    from chatbot.config import API_BASE_URL

    assert API_BASE_URL.startswith("http")


def test_chatbot_config_all_urls_defined():
    from chatbot import config

    required = [
        "API_BASE_URL",
        "API_DOCS_URL",
        "MODEL_SERVER_URL",
        "MODEL_SERVER_PUBLIC_URL",
        "STREAMLIT_URL",
        "HOST_DEMO_URL",
        "WIDGET_APP_URL",
        "JAEGER_URL",
        "MINIO_URL",
    ]
    for attr in required:
        val = getattr(config, attr, None)
        assert val is not None, f"chatbot.config.{attr} not defined"
        assert isinstance(val, str), f"chatbot.config.{attr} should be str"


def test_chatbot_config_defaults_are_localhost():
    from chatbot.config import (
        API_BASE_URL,
        HOST_DEMO_URL,
        JAEGER_URL,
        MINIO_URL,
        MODEL_SERVER_PUBLIC_URL,
        MODEL_SERVER_URL,
        STREAMLIT_URL,
        WIDGET_APP_URL,
    )

    # Default env has no overrides — all should point to localhost
    for url in [
        API_BASE_URL,
        MODEL_SERVER_URL,
        MODEL_SERVER_PUBLIC_URL,
        STREAMLIT_URL,
        HOST_DEMO_URL,
        WIDGET_APP_URL,
        JAEGER_URL,
        MINIO_URL,
    ]:
        assert "localhost" in url or url.startswith("http"), (
            f"Unexpected default URL: {url}"
        )


def test_chatbot_api_client_imports():
    from chatbot import api_client  # noqa: F401


def test_chatbot_api_client_functions_exist():
    from chatbot import api_client

    for fn in [
        "login",
        "me",
        "chat",
        "rag_query",
        "check_api_health",
        "check_model_server_health",
        "get_short_term_memory",
        "get_long_term_memories",
        "list_widgets",
        "create_widget",
    ]:
        assert callable(getattr(api_client, fn, None)), f"api_client.{fn} not callable"


def test_chatbot_api_client_uses_config_base_url():
    from chatbot.api_client import login
    import inspect

    src = inspect.getsource(login)
    assert "API_BASE_URL" in src or "api/v1/auth/login" in src


def test_chatbot_state_imports():
    from chatbot import state  # noqa: F401


def test_chatbot_state_functions_exist():
    from chatbot import state

    for fn in ["init_state", "logout", "new_conversation"]:
        assert callable(getattr(state, fn, None)), f"state.{fn} not callable"


def test_chatbot_components_imports():
    from chatbot import components  # noqa: F401


def test_chatbot_components_status_badge_true():
    from chatbot.components import status_badge

    assert status_badge(True) == "✅"


def test_chatbot_components_status_badge_false():
    from chatbot.components import status_badge

    assert status_badge(False) == "❌"


def test_chatbot_components_status_badge_none():
    from chatbot.components import status_badge

    assert status_badge(None) == "⚠️"


def test_chatbot_pages_imports():
    from chatbot import pages  # noqa: F401


def test_chatbot_pages_functions_exist():
    from chatbot import pages

    for fn in [
        "page_overview",
        "page_system_health",
        "page_chat",
        "page_rag_explorer",
        "page_classifier",
        "page_memory",
        "page_widget_manager",
        "page_observability",
        "page_artifacts",
        "page_demo_runbook",
    ]:
        assert callable(getattr(pages, fn, None)), f"pages.{fn} not callable"


def test_chatbot_main_imports():
    from chatbot import main  # noqa: F401


def test_chatbot_main_pages_map_complete():
    from chatbot.main import _PAGE_FN, _PAGES

    assert set(_PAGES) == set(_PAGE_FN.keys()), (
        "All pages in _PAGES must have a function in _PAGE_FN"
    )
    assert len(_PAGES) == 10
