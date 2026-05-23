"""Reusable UI components for the AI Ops Control Center."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st


def status_badge(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚠️"


def parse_json_if_possible(value: Any) -> Any:
    """Return a parsed object if value looks like JSON, else the original value."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s[:1] in ("{", "["):
            try:
                return json.loads(s)
            except (json.JSONDecodeError, ValueError):
                return value
    return value


def clean_preview_text(text: Any, max_chars: int = 300) -> str:
    """Collapse escaped/real newlines and whitespace into a readable one-line preview."""
    if not isinstance(text, str):
        text = str(text)
    cleaned = text.replace("\\n", " ").replace("\\t", " ").replace("\\r", " ")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "…"
    return cleaned


def render_rag_chunks(results: list[dict]) -> None:
    """Render retrieved RAG chunks as compact, readable cards.

    Works for both the RAG Explorer payload (chunk_id + score present) and the
    chat rag_query tool payload (text + source_type only).
    """
    if not results:
        st.caption("No chunks returned.")
        return
    for i, chunk in enumerate(results, 1):
        source = chunk.get("source_type", "?")
        score = chunk.get("score")
        score_str = f"{score:.4f}" if isinstance(score, (int, float)) else "—"
        text = chunk.get("text", "")
        preview = clean_preview_text(text, 80)
        with st.expander(f"#{i} · [{source}] · score={score_str} — {preview}"):
            chunk_id = chunk.get("chunk_id")
            if chunk_id:
                st.caption(f"chunk_id: `{chunk_id}`")
            # st.text preserves raw newlines/markdown literally — no badge/heading
            # rendering surprises from noisy Kubernetes doc/issue chunks.
            st.text(text)


def render_tool_call(record: dict) -> None:
    """Render a single chat tool-call record as a structured card.

    Falls back to a raw-JSON expander so nothing is hidden.
    """
    name = record.get("tool_name") or record.get("tool") or "tool"
    error = record.get("error")

    if error:
        st.markdown(f"**🔧 `{name}`** — ❌ error")
        st.caption(clean_preview_text(error, 300))
        with st.expander("Show raw JSON"):
            st.json(record)
        return

    parsed = parse_json_if_possible(record.get("result"))
    st.markdown(f"**🔧 `{name}`** — ✅")

    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        # RAG-style payload: {"retriever": ..., "results": [...]}
        st.caption(
            f"retriever: `{parsed.get('retriever', '—')}` · "
            f"results: {len(parsed['results'])}"
        )
        render_rag_chunks(parsed["results"])
    elif isinstance(parsed, dict):
        # classify / entities / summarize style: show fields cleanly
        for key, val in parsed.items():
            st.caption(f"**{key}**: {clean_preview_text(val, 200)}")
    elif parsed is not None:
        st.caption(clean_preview_text(parsed, 400))

    with st.expander("Show raw JSON"):
        st.json(record)
