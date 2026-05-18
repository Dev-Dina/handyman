import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from app.infra.logging import trace_id_var


@dataclass
class Span:
    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    _attributes: dict = field(default_factory=dict, repr=False)

    def set_attribute(self, key: str, value: str) -> None:
        self._attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self._attributes["exception.type"] = type(exc).__name__
        self._attributes["exception.message"] = str(exc)


class NoOpTracer:
    """Local/no-op tracer. Generates real IDs so logs are always traceable.
    Swap for an OTEL tracer when a backend is configured."""

    @contextmanager
    def start_span(self, name: str) -> Generator[Span, None, None]:
        span = Span(name=name)
        token = trace_id_var.set(span.trace_id)
        try:
            yield span
        finally:
            trace_id_var.reset(token)


_tracer: NoOpTracer = NoOpTracer()


def get_tracer() -> NoOpTracer:
    return _tracer
