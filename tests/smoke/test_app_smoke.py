"""Smoke tests: verify app imports and route registration without starting the server."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.smoke


def test_app_imports():
    from app.main import app  # noqa: F401


def test_app_title():
    from app.main import app

    assert app.title == "Maintainer's Copilot API"


def test_healthz_route_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/healthz" in paths


def test_tools_entities_route_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/tools/entities" in paths


def test_tools_summarize_route_registered():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/tools/summarize" in paths


def test_entity_extractor_importable():
    from app.services.tools.entity_extractor import extract_entities  # noqa: F401


def test_redaction_importable():
    from app.infra.redaction import redact  # noqa: F401


def test_ollama_client_importable():
    from app.infra.ollama_client import OllamaClient  # noqa: F401
