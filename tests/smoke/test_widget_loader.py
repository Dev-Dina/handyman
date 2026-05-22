"""Smoke tests for GET /widget.js loader endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.widget_loader import router

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def client() -> TestClient:
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


def test_widget_js_returns_200(client: TestClient) -> None:
    r = client.get("/widget.js")
    assert r.status_code == 200


def test_widget_js_content_type_is_javascript(client: TestClient) -> None:
    r = client.get("/widget.js")
    assert "javascript" in r.headers["content-type"]


def test_widget_js_contains_iframe(client: TestClient) -> None:
    r = client.get("/widget.js")
    assert "iframe" in r.text


def test_widget_js_contains_postmessage_listener(client: TestClient) -> None:
    r = client.get("/widget.js")
    assert "handyman-widget-resize" in r.text


def test_widget_js_validates_message_source(client: TestClient) -> None:
    r = client.get("/widget.js")
    assert "event.source" in r.text


def test_widget_js_no_secrets(client: TestClient) -> None:
    content = client.get("/widget.js").text.lower()
    assert "api_key" not in content
    assert "password" not in content
    assert "secret" not in content


def test_widget_loader_importable() -> None:
    from app.services.widgets.loader import build_loader_script  # noqa: F401


def test_build_loader_script_returns_string() -> None:
    from app.services.widgets.loader import build_loader_script

    js = build_loader_script()
    assert isinstance(js, str)
    assert len(js) > 100


def test_build_loader_script_no_template_placeholder() -> None:
    from app.services.widgets.loader import build_loader_script

    js = build_loader_script()
    assert "__WIDGET_APP_PATH__" not in js


def test_build_loader_script_contains_widget_app_path() -> None:
    from app.services.widgets.loader import WIDGET_APP_PATH, build_loader_script

    js = build_loader_script()
    assert WIDGET_APP_PATH in js
    assert "/widget-app/" in js


def test_build_loader_script_reads_data_widget_url() -> None:
    """Loader must read data-widget-url so Docker widget nginx (port 3000) is used."""
    from app.services.widgets.loader import build_loader_script

    js = build_loader_script()
    assert "data-widget-url" in js, (
        "Loader must read data-widget-url attribute — "
        "without it, iframe falls back to API /widget-app/ which returns 404 in Docker"
    )


def test_build_loader_script_reads_data_api_base_url() -> None:
    """Loader must read data-api-base-url so widget React app calls the correct API."""
    from app.services.widgets.loader import build_loader_script

    js = build_loader_script()
    assert "data-api-base-url" in js, (
        "Loader must read data-api-base-url attribute — "
        "widget React app uses this to call POST /api/v1/chat"
    )


def test_build_loader_script_passes_api_base_to_iframe() -> None:
    """Loader must append api_base to the iframe URL so the widget knows where to call."""
    from app.services.widgets.loader import build_loader_script

    js = build_loader_script()
    assert "api_base" in js, (
        "Loader must include api_base in the iframe src query string — "
        "widget reads it via URL params to call the correct API endpoint"
    )
