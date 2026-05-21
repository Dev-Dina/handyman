import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from app.infra.logging import trace_id_var

# Tracks the span_id of the currently-active span so nested spans can reference it
_active_span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_span_id", default=""
)


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
    Swap for an OTEL tracer when a backend is configured."""

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


_tracer: NoOpTracer = NoOpTracer()


def get_tracer() -> NoOpTracer:
    return _tracer
