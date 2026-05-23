"""Unit tests for app.services.rag.retrieval — thin-chunk filter and extractive answer."""

from __future__ import annotations

import pytest

from app.services.rag.retrieval import (
    _ANSWER_MAX_CHARS,
    _apply_thin_filter,
    _is_thin_chunk,
    build_extractive_answer,
)

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_THIN = {"text": "## Services", "score": 0.9}
_SUBSTANTIVE = {
    "text": "Pod scheduling in Kubernetes places workloads on nodes based on resource requests.",
    "score": 0.7,
}
_ANOTHER_SUBSTANTIVE = {
    "text": "A Deployment provides declarative updates for Pods and ReplicaSets.",
    "score": 0.5,
}


# ---------------------------------------------------------------------------
# _is_thin_chunk
# ---------------------------------------------------------------------------


def test_heading_only_is_thin():
    assert _is_thin_chunk("## Services") is True


def test_heading_with_body_not_thin():
    # Text must be >= THIN_CHUNK_MIN_BODY_CHARS (80) to clear the length gate
    text = "## Services\n\nThis section explains Kubernetes services, networking, and load balancing in detail."
    assert _is_thin_chunk(text) is False


def test_long_heading_only_not_thin():
    long_heading = "## " + "x" * 100
    assert _is_thin_chunk(long_heading) is False


def test_plain_text_not_thin():
    assert _is_thin_chunk("Pod scheduling in Kubernetes.") is False


def test_empty_text_not_thin():
    assert _is_thin_chunk("") is False


# ---------------------------------------------------------------------------
# _apply_thin_filter
# ---------------------------------------------------------------------------


def test_thin_excluded_when_substantive_exists():
    result = _apply_thin_filter([_THIN, _SUBSTANTIVE])
    assert all(c["text"] != _THIN["text"] for c in result)
    assert any(c["text"] == _SUBSTANTIVE["text"] for c in result)


def test_thin_retained_when_all_thin():
    thin1 = {"text": "## A", "score": 0.9}
    thin2 = {"text": "## B", "score": 0.8}
    result = _apply_thin_filter([thin1, thin2])
    assert len(result) == 2


def test_result_order_preserved_by_score():
    chunks = [
        {"text": "Pod scheduling works via the scheduler.", "score": 0.9},
        {"text": "## Services", "score": 0.95},
        {"text": "A Deployment provides declarative updates.", "score": 0.7},
    ]
    result = _apply_thin_filter(chunks)
    scores = [c["score"] for c in result]
    assert scores == sorted(scores, reverse=True)


def test_all_substantive_unchanged():
    chunks = [_SUBSTANTIVE, _ANOTHER_SUBSTANTIVE]
    result = _apply_thin_filter(chunks)
    assert len(result) == 2


def test_empty_input_returns_empty():
    assert _apply_thin_filter([]) == []


# ---------------------------------------------------------------------------
# build_extractive_answer
# ---------------------------------------------------------------------------


def test_returns_text_from_substantive_chunk():
    answer = build_extractive_answer([_SUBSTANTIVE])
    assert answer is not None
    assert "Pod scheduling" in answer


def test_returns_none_when_empty():
    assert build_extractive_answer([]) is None


def test_returns_none_when_all_thin():
    assert build_extractive_answer([_THIN]) is None


def test_truncates_to_max_chars():
    long_text = "x" * (_ANSWER_MAX_CHARS + 500)
    chunk = {"text": long_text, "score": 0.9}
    answer = build_extractive_answer([chunk])
    assert answer is not None
    assert len(answer) <= _ANSWER_MAX_CHARS


def test_uses_multiple_chunks():
    answer = build_extractive_answer([_SUBSTANTIVE, _ANOTHER_SUBSTANTIVE])
    assert answer is not None
    assert "Pod scheduling" in answer
    assert "Deployment" in answer


def test_thin_chunks_excluded_from_answer():
    answer = build_extractive_answer([_THIN, _SUBSTANTIVE])
    assert answer is not None
    assert "## Services" not in answer


# ---------------------------------------------------------------------------
# Live hybrid wiring (mocked corpus + model_server /embed — no torch, no network)
# ---------------------------------------------------------------------------

_FAKE_CORPUS = [
    {"chunk_id": "c1", "text": "pods run containers on nodes", "source_type": "docs"},
    {"chunk_id": "c2", "text": "services expose pods over the network", "source_type": "docs"},
]


def test_runtime_chunk_embeddings_path_is_shipped_artifact():
    from app.services.rag.config import RAG_CHUNK_EMBEDDINGS_PATH

    p = str(RAG_CHUNK_EMBEDDINGS_PATH).replace("\\", "/")
    assert p.endswith("artifacts/rag/intfloat_e5_small_v2_chunks.npy")


def test_no_torch_import_in_retrieval():
    import sys

    import app.services.rag.retrieval  # noqa: F401

    assert "torch" not in sys.modules, "torch must not be imported by the API retrieval path"


def _reset_caches(monkeypatch, chunk_vecs):
    import numpy as np

    from app.services.rag import retrieval as r

    monkeypatch.setattr(r, "_chunks", None)
    monkeypatch.setattr(r, "_tfidf_vec", None)
    monkeypatch.setattr(r, "_tfidf_mat", None)
    monkeypatch.setattr(r, "_chunk_vecs", None)
    monkeypatch.setattr(r, "_load_chunks", lambda: _FAKE_CORPUS)
    monkeypatch.setattr(r, "_load_chunk_vecs", lambda: chunk_vecs)
    return np


async def test_hybrid_used_when_embeddings_and_embed_available(monkeypatch):
    import numpy as np

    _reset_caches(monkeypatch, np.eye(2, 384, dtype=np.float32))

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def embed(self, texts, model):
            return [[1.0] + [0.0] * 383]

    monkeypatch.setattr(
        "app.infra.modelserver_client.ModelServerClient", _FakeClient
    )
    from app.services.rag.retrieval import retrieve

    chunks, mode = await retrieve("what are services", top_k=2, alpha=0.7)
    assert mode == "hybrid"
    assert len(chunks) >= 1


async def test_fallback_to_tfidf_when_embed_unavailable(monkeypatch):
    import numpy as np

    _reset_caches(monkeypatch, np.eye(2, 384, dtype=np.float32))
    from app.domain.errors import ModelServerUnavailableError

    class _DownClient:
        def __init__(self, *a, **k):
            pass

        async def embed(self, texts, model):
            raise ModelServerUnavailableError("model server down")

    monkeypatch.setattr(
        "app.infra.modelserver_client.ModelServerClient", _DownClient
    )
    from app.services.rag.retrieval import retrieve

    chunks, mode = await retrieve("what are services", top_k=2, alpha=0.7)
    assert mode == "tfidf_fallback"


async def test_fallback_when_no_chunk_embeddings(monkeypatch):
    _reset_caches(monkeypatch, None)
    from app.services.rag.retrieval import retrieve

    chunks, mode = await retrieve("what are services", top_k=2, alpha=0.7)
    assert mode == "tfidf_fallback"


async def test_source_type_filter_preserved_in_hybrid(monkeypatch):
    import numpy as np

    _reset_caches(monkeypatch, np.eye(2, 384, dtype=np.float32))

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def embed(self, texts, model):
            return [[1.0] + [0.0] * 383]

    monkeypatch.setattr(
        "app.infra.modelserver_client.ModelServerClient", _FakeClient
    )
    from app.services.rag.retrieval import retrieve

    chunks, mode = await retrieve(
        "services", top_k=2, alpha=0.7, source_type="docs", query_transform="technical_terms"
    )
    assert all(c["source_type"] == "docs" for c in chunks)
