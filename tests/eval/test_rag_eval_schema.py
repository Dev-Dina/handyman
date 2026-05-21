"""Eval tests: RAG eval harness schema, threshold guards, and safety contracts."""

from __future__ import annotations

import json

import pytest
import yaml

from app.core.paths import PROJECT_ROOT
from app.services.rag.config import RAG_API_EVAL_REPORT_PATH, RAG_GOLDEN_PATH

pytestmark = pytest.mark.eval

_THRESHOLDS_PATH = PROJECT_ROOT / "eval_thresholds.yaml"
_RETRIEVAL_SRC = PROJECT_ROOT / "app" / "services" / "rag" / "retrieval.py"
_EVAL_API_SRC = PROJECT_ROOT / "pipelines" / "rag" / "eval_api.py"

_REPORT_REQUIRED_KEYS = {
    "generated_at",
    "golden_path",
    "n_questions",
    "alpha",
    "retrieval_mode",
    "hit_at_5",
    "recall_at_5",
    "mrr_at_10",
    "per_question",
}


# ---------------------------------------------------------------------------
# Threshold file
# ---------------------------------------------------------------------------


def test_thresholds_file_exists():
    assert _THRESHOLDS_PATH.exists(), f"Missing: {_THRESHOLDS_PATH}"


def test_thresholds_nonzero():
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    assert cfg["classification"]["macro_f1_min"] > 0, (
        "classification.macro_f1_min must be > 0"
    )
    assert cfg["rag"]["hit_at_5_min"] > 0, "rag.hit_at_5_min must be > 0"
    assert cfg["rag"]["mrr_at_10_min"] > 0, "rag.mrr_at_10_min must be > 0"


def test_thresholds_below_one():
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    assert cfg["classification"]["macro_f1_min"] < 1.0
    assert cfg["rag"]["hit_at_5_min"] < 1.0
    assert cfg["rag"]["mrr_at_10_min"] < 1.0


# ---------------------------------------------------------------------------
# No-torch contract
# ---------------------------------------------------------------------------


def test_retrieval_does_not_import_torch():
    src = _RETRIEVAL_SRC.read_text(encoding="utf-8")
    assert "import torch" not in src, (
        "retrieval.py must not import torch at module level"
    )
    assert "from torch" not in src, (
        "retrieval.py must not import from torch at module level"
    )


def test_eval_api_does_not_import_torch():
    src = _EVAL_API_SRC.read_text(encoding="utf-8")
    assert "import torch" not in src
    assert "from torch" not in src


# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------


def test_eval_api_importable():
    import pipelines.rag.eval_api  # noqa: F401


def test_query_transform_importable():
    from app.services.rag.query_transform import apply  # noqa: F401


def test_tracer_importable():
    from app.infra.tracing import get_tracer  # noqa: F401


def test_tracer_noop_works_without_backend():
    from app.infra.tracing import get_tracer

    tracer = get_tracer()
    with tracer.start_span("test.span") as span:
        span.set_attribute("key", "value")
    # No exception = NoOpTracer is structurally ready


# ---------------------------------------------------------------------------
# Query transform
# ---------------------------------------------------------------------------


def test_query_transform_none_is_identity():
    from app.services.rag.query_transform import apply

    q = "How do I debug a pod crash?"
    assert apply(q, "none") == q


def test_query_transform_technical_terms_expands():
    from app.services.rag.query_transform import apply

    q = "How do services work in Kubernetes?"
    expanded = apply(q, "technical_terms")
    assert expanded.startswith(q) or len(expanded) > len(q)
    assert "service" in expanded.lower()


# ---------------------------------------------------------------------------
# Thin chunk filter
# ---------------------------------------------------------------------------


def test_thin_chunk_filter_demotes_headings():
    from app.services.rag.retrieval import _apply_thin_filter, _is_thin_chunk

    heading = {
        "chunk_id": "h1",
        "text": "## Services",
        "source_type": "docs",
        "score": 0.9,
    }
    body = {
        "chunk_id": "b1",
        "text": "The Service API, part of Kubernetes, is an abstraction to help you expose groups of Pods over a network.",
        "source_type": "docs",
        "score": 0.7,
    }
    assert _is_thin_chunk(heading["text"])
    assert not _is_thin_chunk(body["text"])

    result = _apply_thin_filter([heading, body])
    assert len(result) == 1, (
        "thin chunk should be excluded when substantive chunk exists"
    )
    assert result[0]["chunk_id"] == "b1", "body chunk should be the only result"


def test_thin_chunk_filter_preserves_all_chunks():
    from app.services.rag.retrieval import _apply_thin_filter

    chunks = [
        {"chunk_id": f"c{i}", "text": "## Heading", "source_type": "docs", "score": 0.5}
        for i in range(3)
    ]
    result = _apply_thin_filter(chunks)
    assert len(result) == 3


def test_thin_chunk_filter_noop_when_all_substantive():
    from app.services.rag.retrieval import _apply_thin_filter

    chunks = [
        {
            "chunk_id": "a",
            "text": "Kubernetes is an open-source container orchestration platform that automates deployment.",
            "source_type": "docs",
            "score": 0.9,
        },
        {
            "chunk_id": "b",
            "text": "A Pod is the smallest deployable unit in Kubernetes and can contain one or more containers.",
            "source_type": "docs",
            "score": 0.8,
        },
    ]
    result = _apply_thin_filter(chunks)
    assert [c["chunk_id"] for c in result] == ["a", "b"]


# ---------------------------------------------------------------------------
# Golden set
# ---------------------------------------------------------------------------


def test_rag_golden_exists():
    assert RAG_GOLDEN_PATH.exists(), f"Missing golden set: {RAG_GOLDEN_PATH}"


# ---------------------------------------------------------------------------
# Eval report (conditional — requires prior run of eval_api)
# ---------------------------------------------------------------------------


def test_api_eval_report_schema_if_present():
    if not RAG_API_EVAL_REPORT_PATH.exists():
        pytest.skip("api_eval_report.json not yet generated — run eval_api first")
    with open(RAG_API_EVAL_REPORT_PATH, encoding="utf-8") as fh:
        report = json.load(fh)
    missing = _REPORT_REQUIRED_KEYS - set(report.keys())
    assert not missing, f"Report missing keys: {missing}"
    assert report["n_questions"] > 0
    assert 0.0 <= report["hit_at_5"] <= 1.0
    assert 0.0 <= report["recall_at_5"] <= 1.0
    assert 0.0 <= report["mrr_at_10"] <= 1.0
    assert isinstance(report["per_question"], list)
    assert len(report["per_question"]) == report["n_questions"]


def test_api_eval_report_meets_thresholds_if_present():
    if not RAG_API_EVAL_REPORT_PATH.exists():
        pytest.skip("api_eval_report.json not yet generated — run eval_api first")
    with open(_THRESHOLDS_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    with open(RAG_API_EVAL_REPORT_PATH, encoding="utf-8") as fh:
        report = json.load(fh)
    hit_min = cfg["rag"]["hit_at_5_min"]
    mrr_min = cfg["rag"]["mrr_at_10_min"]
    assert report["hit_at_5"] >= hit_min, (
        f"hit@5 {report['hit_at_5']} below threshold {hit_min}"
    )
    assert report["mrr_at_10"] >= mrr_min, (
        f"mrr@10 {report['mrr_at_10']} below threshold {mrr_min}"
    )
