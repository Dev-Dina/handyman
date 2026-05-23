"""Unit tests for model_server /embed (mocked embedder — no torch / no model load)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    from model_server.main import app

    return TestClient(app)


def test_embed_returns_vectors(client, monkeypatch):
    monkeypatch.setattr(
        "model_server.main.embed_texts",
        lambda texts: [[0.1] * 384 for _ in texts],
    )
    r = client.post("/embed", json={"texts": ["query: what are services", "query: x"]})
    assert r.status_code == 200
    data = r.json()
    assert data["dimension"] == 384
    assert len(data["embeddings"]) == 2
    assert len(data["embeddings"][0]) == 384
    assert data["model"]


def test_embed_requires_texts(client):
    r = client.post("/embed", json={"texts": []})
    assert r.status_code == 422  # min_length=1


def test_embed_unavailable_returns_503(client, monkeypatch):
    from model_server.embedder import EmbedderUnavailableError

    def _raise(_texts):
        raise EmbedderUnavailableError("transformers/torch not installed in this image")

    monkeypatch.setattr("model_server.main.embed_texts", _raise)
    r = client.post("/embed", json={"texts": ["query: hi"]})
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "embedder_unavailable"


def test_resolve_model_ref_prefers_local_dir(monkeypatch):
    import model_server.embedder as emb

    monkeypatch.setattr("os.path.isdir", lambda p: True)
    assert emb._resolve_model_ref() == emb.EMBED_MODEL_PATH


def test_resolve_model_ref_falls_back_to_hub_id(monkeypatch):
    import model_server.embedder as emb

    monkeypatch.setattr("os.path.isdir", lambda p: False)
    assert emb._resolve_model_ref() == emb.EMBED_MODEL_NAME


def test_classify_still_present():
    """/embed addition must not remove the classifier route."""
    from model_server.main import app

    paths = {route.path for route in app.routes}
    assert "/classify" in paths
    assert "/embed" in paths
    assert "/healthz" in paths
