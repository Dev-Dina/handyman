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
