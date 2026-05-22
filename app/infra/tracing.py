"""Tracing adapter.

Default: NoOpTracer — generates real IDs for log correlation, emits no spans to a backend.
OTEL mode: when OTEL_EXPORTER_OTLP_ENDPOINT is set, a real TracerProvider with OTLP HTTP
exporter sends spans to Jaeger (or any OTEL-compatible collector).

Call configure_tracing() once at app startup to switch from NoOp to OTEL.
"""

from __future__ import annotations

import contextvars
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from app.infra.logging import trace_id_var

# Tracks the span_id of the currently-active span so nested spans can reference it.
# Only used by NoOpTracer; OtelTracerWrapper relies on OTEL context propagation.
_active_span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_span_id", default=""
)

_OTEL_SERVICE_NAME: str = "handyman-api"
_OTEL_ENDPOINT_ENV: str = "OTEL_EXPORTER_OTLP_ENDPOINT"


# ---------------------------------------------------------------------------
# NoOpTracer — default; structurally OTEL-ready; no export backend required
# ---------------------------------------------------------------------------


@dataclass
class Span:
    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_span_id: str = ""
    _attributes: dict = field(default_factory=dict, repr=False)

    def set_attribute(self, key: str, value: str) -> None:
        self._attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self._attributes["exception.type"] = type(exc).__name__
        self._attributes["exception.message"] = str(exc)


class NoOpTracer:
    """Local/no-op tracer. Generates real IDs so logs are always traceable.
    Nested spans reuse the active trace_id so all spans for one request are joinable.
    Swap for OtelTracerWrapper when a backend is configured."""

    @contextmanager
    def start_span(self, name: str) -> Generator[Span, None, None]:
        existing_trace_id = trace_id_var.get()
        trace_id = existing_trace_id if existing_trace_id else uuid.uuid4().hex
        parent_span_id = _active_span_id_var.get()

        span = Span(name=name, trace_id=trace_id, parent_span_id=parent_span_id)

        trace_token = trace_id_var.set(trace_id)
        span_token = _active_span_id_var.set(span.span_id)
        try:
            yield span
        finally:
            _active_span_id_var.reset(span_token)
            trace_id_var.reset(trace_token)


# ---------------------------------------------------------------------------
# OtelTracerWrapper — used when OTEL_EXPORTER_OTLP_ENDPOINT is set
# ---------------------------------------------------------------------------


class OtelTracerWrapper:
    """Wraps an OTEL tracer with the same start_span(name) context-manager interface.

    - Sets trace_id_var from the OTEL span context so log correlation works.
    - Yields the raw OTEL span; callers use set_attribute() and record_exception()
      which OTEL spans implement natively.
    - Resets trace_id_var on span exit to preserve NoOpTracer semantics.
    """

    def __init__(self, otel_tracer: Any) -> None:
        self._otel_tracer = otel_tracer

    @contextmanager
    def start_span(self, name: str) -> Generator[Any, None, None]:
        with self._otel_tracer.start_as_current_span(name) as otel_span:
            ctx = otel_span.get_span_context()
            trace_id_hex = (
                format(ctx.trace_id, "032x") if ctx.is_valid else uuid.uuid4().hex
            )
            token = trace_id_var.set(trace_id_hex)
            try:
                yield otel_span
            finally:
                trace_id_var.reset(token)


# ---------------------------------------------------------------------------
# Global tracer — NoOpTracer by default; replaced by configure_tracing()
# ---------------------------------------------------------------------------

_tracer: NoOpTracer | OtelTracerWrapper = NoOpTracer()


def get_tracer() -> NoOpTracer | OtelTracerWrapper:
    return _tracer


def configure_tracing(service_name: str = _OTEL_SERVICE_NAME) -> None:
    """Switch to OTEL-based tracing when OTEL_EXPORTER_OTLP_ENDPOINT is set.

    Requires opentelemetry-exporter-otlp-proto-http. If the package is absent or
    the endpoint env var is not set, stays with NoOpTracer — no exporter, no background
    threads, no shutdown errors.
    Safe to call multiple times; no-op when endpoint is not configured.
    """
    global _tracer

    endpoint = os.getenv(_OTEL_ENDPOINT_ENV, "").strip()
    if not endpoint:
        return

    try:
        from opentelemetry import trace as otel_trace  # noqa: PLC0415
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # noqa: PLC0415
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        otel_trace.set_tracer_provider(provider)
        _tracer = OtelTracerWrapper(otel_trace.get_tracer(service_name))

    except ImportError:
        pass  # OTLP package not installed — keep NoOpTracer, no background threads
    except Exception:  # noqa: BLE001
        pass  # keep NoOpTracer; app must not crash on tracing init failure
