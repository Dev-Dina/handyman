"""Shared constants and table renderers for the AI Ops Control Center pages.

Centralizes the metric tables, tool lists, and report paths reused across
multiple page modules so no page redefines them inline.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# ── Metric tables ────────────────────────────────────────────────────────────

CLASSIFIER_METRICS = [
    ("CodeBERT (primary)", "0.7500", "0.7061", "PRIMARY"),
    ("LogisticRegression TF-IDF (fallback)", "0.7139", "0.6938", "FALLBACK"),
    ("Ollama llama3 (baseline)", "0.5850", "0.5554", "BASELINE"),
    ("CI LR golden (25 examples)", "0.7200", "0.6691", "CI gate"),
]

RAG_METRICS = [
    ("E5 hybrid alpha=0.7 (served via /embed)", "0.68", "0.329"),
    ("TF-IDF (CI gate / fallback)", "0.40", "0.196"),
]

JAEGER_SPANS = {
    "chat.request": "Entire chat request lifecycle",
    "llm.groq.chat": "Groq LLM API call (latency, token count)",
    "tool.rag_query": "RAG tool execution",
    "rag.retrieve": "Chunk retrieval step inside RAG",
    "tool.classify_issue": "Classifier tool execution",
    "tool.write_memory": "Memory write tool",
}

MINIO_BUCKETS = ["handyman-artifacts", "handyman-evals"]

ALL_TOOLS = [
    "rag_query",
    "classify_issue",
    "write_memory",
    "summarize",
    "extract_entities",
]

RETRIEVER_OPTIONS = ["auto", "hybrid", "tfidf"]
QUERY_TRANSFORM_OPTIONS = ["none", "technical_terms"]
SOURCE_TYPE_OPTIONS = ["(any)", "doc", "issue", "comment"]

ARTIFACT_MANIFEST = Path("reports/artifact_manifest.json")
RAG_API_EVAL_REPORT = Path("reports/rag/api_eval_report.json")
GENERATION_EVAL_REPORT = Path("reports/rag/generation_eval_report.json")

EMBED_SNIPPET_TEMPLATE = (
    '<script src="{api_base}/widget.js"\n'
    '  data-widget-id="{widget_id}"\n'
    '  data-widget-url="{widget_app_url}"\n'
    '  data-api-base-url="{api_base}"></script>'
)


# ── Reusable table renderers ─────────────────────────────────────────────────


def render_classifier_metrics_table() -> None:
    """Render the official classifier comparison table (model / acc / F1 / role)."""
    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown("**Model**")
    cols[1].markdown("**Accuracy**")
    cols[2].markdown("**Macro-F1**")
    cols[3].markdown("**Role**")
    for model, acc, f1, role in CLASSIFIER_METRICS:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(model)
        cols[1].write(acc)
        cols[2].write(f1)
        cols[3].write(role)


def render_rag_metrics_table() -> None:
    """Render the RAG retrieval metrics table (pipeline / hit@5 / mrr@10)."""
    cols = st.columns([3, 1, 1])
    cols[0].markdown("**Pipeline**")
    cols[1].markdown("**Hit@5**")
    cols[2].markdown("**MRR@10**")
    for pipeline, h5, mrr in RAG_METRICS:
        cols = st.columns([3, 1, 1])
        cols[0].write(pipeline)
        cols[1].write(h5)
        cols[2].write(mrr)
