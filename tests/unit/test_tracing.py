"""Unit tests: NoOpTracer trace propagation correctness."""

from __future__ import annotations

import pytest

from app.infra.logging import trace_id_var
from app.infra.tracing import _active_span_id_var, get_tracer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_trace_vars():
    """Ensure context vars are clean before each test."""
    t = trace_id_var.set("")
    s = _active_span_id_var.set("")
    yield
    trace_id_var.reset(t)
    _active_span_id_var.reset(s)


def test_root_span_creates_trace_id():
    tracer = get_tracer()
    with tracer.start_span("root") as span:
        assert span.trace_id != ""
        assert span.span_id != ""
        assert span.parent_span_id == ""


def test_nested_spans_share_trace_id():
    tracer = get_tracer()
    with tracer.start_span("outer") as outer:
        outer_trace = outer.trace_id
        with tracer.start_span("inner") as inner:
            assert inner.trace_id == outer_trace, (
                "nested span must reuse parent trace_id"
            )


def test_nested_span_has_parent_span_id():
    tracer = get_tracer()
    with tracer.start_span("outer") as outer:
        with tracer.start_span("inner") as inner:
            assert inner.parent_span_id == outer.span_id


def test_deeply_nested_spans_all_share_trace_id():
    tracer = get_tracer()
    with tracer.start_span("l1") as l1:
        with tracer.start_span("l2") as l2:
            with tracer.start_span("l3") as l3:
                assert l2.trace_id == l1.trace_id
                assert l3.trace_id == l1.trace_id


def test_sibling_spans_share_trace_id():
    tracer = get_tracer()
    with tracer.start_span("root") as root:
        root_trace = root.trace_id
        with tracer.start_span("child_a") as child_a:
            pass
        with tracer.start_span("child_b") as child_b:
            pass
    assert child_a.trace_id == root_trace
    assert child_b.trace_id == root_trace


def test_sibling_spans_have_different_span_ids():
    tracer = get_tracer()
    with tracer.start_span("root"):
        with tracer.start_span("child_a") as child_a:
            pass
        with tracer.start_span("child_b") as child_b:
            pass
    assert child_a.span_id != child_b.span_id


def test_trace_id_var_reset_after_root_span_exit():
    tracer = get_tracer()
    with tracer.start_span("root"):
        pass
    assert trace_id_var.get() == ""


def test_active_span_id_var_reset_after_span_exit():
    tracer = get_tracer()
    with tracer.start_span("root"):
        pass
    assert _active_span_id_var.get() == ""


def test_trace_id_var_reset_after_nested_span_exit():
    tracer = get_tracer()
    with tracer.start_span("outer") as outer:
        outer_trace = outer.trace_id
        with tracer.start_span("inner"):
            pass
        # after inner exits, trace_id_var should be back to outer's trace_id
        assert trace_id_var.get() == outer_trace
    assert trace_id_var.get() == ""


def test_consecutive_root_spans_create_different_trace_ids():
    tracer = get_tracer()
    with tracer.start_span("req_1") as s1:
        t1 = s1.trace_id
    with tracer.start_span("req_2") as s2:
        t2 = s2.trace_id
    assert t1 != t2


def test_span_record_exception():
    tracer = get_tracer()
    with tracer.start_span("op") as span:
        exc = ValueError("something went wrong")
        span.record_exception(exc)
    assert span._attributes["exception.type"] == "ValueError"
    assert span._attributes["exception.message"] == "something went wrong"


def test_rag_noop_tracer_integration():
    """RAG span pattern works end-to-end with NoOpTracer (no real backend needed)."""
    tracer = get_tracer()
    trace_ids: list[str] = []

    with tracer.start_span("rag.query") as outer:
        trace_ids.append(outer.trace_id)
        with tracer.start_span("rag.retrieve") as retrieve_span:
            retrieve_span.set_attribute("top_k", "5")
            trace_ids.append(retrieve_span.trace_id)
            with tracer.start_span("rag.metadata_filter") as mf:
                mf.set_attribute("chunk_count", "2189")
                trace_ids.append(mf.trace_id)
            with tracer.start_span("rag.tfidf_fallback"):
                trace_ids.append(trace_id_var.get())

    assert len(set(trace_ids)) == 1, "all RAG spans must share one trace_id per request"
    assert trace_id_var.get() == ""
