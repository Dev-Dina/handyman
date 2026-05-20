"""Tool services: entity extraction and summarization."""

from __future__ import annotations

from app.services.tools.entity_extractor import extract_entities
from app.services.tools.summarizer import summarize as _summarize


def extract_entities_service(text: str) -> dict:
    """Run rule-based NER and return entities grouped by type with total count.

    Deterministic, synchronous, no external calls.
    """
    entities = extract_entities(text)
    total_count = sum(len(v) for v in entities.values())
    return {"entities_by_type": entities, "total_count": total_count}


async def summarize_service(text: str, *, max_chars: int | None = None) -> dict:
    """Summarize text using the local Ollama LLM.

    Returns {summary, model, latency_seconds}.
    Raises OllamaUnavailableError if Ollama cannot be reached.
    """
    return await _summarize(text, max_chars=max_chars)
