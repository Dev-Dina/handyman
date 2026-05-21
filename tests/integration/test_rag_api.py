"""Integration tests: /api/v1/rag/query endpoint behavior with mocked retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.rag import router
from app.domain.errors import RagCorpusNotReadyError

pytestmark = pytest.mark.integration

_MOCK_CHUNK = {
    "chunk_id": "chunk_001",
    "text": "Pod scheduling in Kubernetes places workloads on nodes based on resource requests.",
    "source_type": "docs",
    "score": 0.85,
}


@pytest.fixture(scope="module")
def client():
    test_app = FastAPI()
    test_app.include_router(router)
    with TestClient(test_app) as c:
        yield c


def test_rag_query_ok(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
    ):
        resp = client.post(
            "/api/v1/rag/query", json={"question": "How does pod scheduling work?"}
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["retriever_used"] == "hybrid"
    assert "latency_seconds" in data


def test_rag_query_tfidf_mode(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "tfidf")),
    ):
        resp = client.post(
            "/api/v1/rag/query",
            json={"question": "kubectl get pods", "retriever": "tfidf"},
        )
    assert resp.status_code == 200
    assert resp.json()["retriever_used"] == "tfidf"


def test_rag_query_tfidf_fallback(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "tfidf_fallback")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": "kubectl get pods"})
    assert resp.status_code == 200
    assert resp.json()["retriever_used"] == "tfidf_fallback"


def test_rag_query_corpus_not_ready_returns_503(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(side_effect=RagCorpusNotReadyError("corpus missing")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": "any question"})
    assert resp.status_code == 503


def test_rag_query_empty_question_rejected(client):
    resp = client.post("/api/v1/rag/query", json={"question": ""})
    assert resp.status_code == 422


def test_rag_query_missing_question_rejected(client):
    resp = client.post("/api/v1/rag/query", json={})
    assert resp.status_code == 422


def test_rag_query_top_k_respected(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
    ):
        resp = client.post(
            "/api/v1/rag/query", json={"question": "namespace issues", "top_k": 3}
        )
    assert resp.status_code == 200
    assert resp.json()["top_k"] == 3


def test_rag_query_response_shape(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": "pod crash loop"})
    data = resp.json()
    assert "question" in data
    assert "results" in data
    assert "retriever_used" in data
    assert "query_transform_used" in data
    assert "top_k" in data
    assert "answer" in data
    assert "latency_seconds" in data
    chunk = data["results"][0]
    assert "chunk_id" in chunk
    assert "text" in chunk
    assert "source_type" in chunk
    assert "score" in chunk


def test_rag_query_top_k_out_of_range_rejected(client):
    resp = client.post("/api/v1/rag/query", json={"question": "test", "top_k": 0})
    assert resp.status_code == 422


def test_rag_query_question_returned_in_response(client):
    question = "What are pod disruption budgets?"
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": question})
    assert resp.json()["question"] == question


def test_rag_query_answer_field_present(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "hybrid")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": "pod restarts"})
    data = resp.json()
    assert "answer" in data  # answer field is present (may be null pre-generation)


def test_rag_query_unexpected_error_returns_500(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(side_effect=RuntimeError("unexpected internal failure")),
    ):
        resp = client.post("/api/v1/rag/query", json={"question": "any question"})
    assert resp.status_code == 500
    assert "detail" in resp.json()


def test_rag_query_source_type_filter_passed_through(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "tfidf_fallback")),
    ) as mock_retrieve:
        resp = client.post(
            "/api/v1/rag/query",
            json={"question": "pod issue", "source_type": "docs"},
        )
    assert resp.status_code == 200
    _, kwargs = mock_retrieve.call_args
    assert kwargs.get("source_type") == "docs"


def test_rag_query_maintainer_only_filter_passed_through(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "tfidf_fallback")),
    ) as mock_retrieve:
        resp = client.post(
            "/api/v1/rag/query",
            json={"question": "maintainer response", "maintainer_only": True},
        )
    assert resp.status_code == 200
    _, kwargs = mock_retrieve.call_args
    assert kwargs.get("maintainer_only") is True


def test_rag_query_transform_passed_through(client):
    with patch(
        "app.api.routes.rag.retrieve",
        new=AsyncMock(return_value=([_MOCK_CHUNK], "tfidf")),
    ) as mock_retrieve:
        resp = client.post(
            "/api/v1/rag/query",
            json={
                "question": "namespace services",
                "query_transform": "technical_terms",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["query_transform_used"] == "technical_terms"
    _, kwargs = mock_retrieve.call_args
    assert kwargs.get("query_transform") == "technical_terms"
