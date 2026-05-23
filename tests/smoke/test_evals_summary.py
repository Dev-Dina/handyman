"""Smoke tests for GET /api/v1/evals/summary (reads local report files)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.evals import router

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_summary_returns_200_and_sections(client: TestClient) -> None:
    r = client.get("/api/v1/evals/summary")
    assert r.status_code == 200
    data = r.json()
    for section in (
        "classifier",
        "rag_retrieval",
        "generation_deterministic",
        "generation_judge",
    ):
        assert section in data


def test_summary_classifier_served_model(client: TestClient) -> None:
    data = client.get("/api/v1/evals/summary").json()
    assert data["classifier"]["served_model"] == "LogisticRegression TF-IDF"
    assert data["classifier"]["status"] == "deployed"


def test_summary_status_fields_are_known(client: TestClient) -> None:
    data = client.get("/api/v1/evals/summary").json()
    assert data["generation_deterministic"]["status"] in ("deployed", "gap")
    assert data["generation_judge"]["status"] in ("deployed", "gap")
    assert "offline_best_e5_hybrid" in data["rag_retrieval"]
