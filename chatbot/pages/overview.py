"""Overview page — what the system is, architecture, and headline metrics."""

from __future__ import annotations

import streamlit as st

from chatbot.components import page_proves, render_widget_preview
from chatbot.config import (
    API_DOCS_URL,
    DEFAULT_WIDGET_ID,
    HOST_DEMO_URL,
    JAEGER_URL,
    MINIO_URL,
    STREAMLIT_URL,
    WIDGET_APP_URL,
)
from chatbot.pages._shared import (
    render_classifier_metrics_table,
    render_rag_metrics_table,
)


def page_overview() -> None:
    st.title("Maintainer's Copilot — AI Ops Control Center")
    page_proves(
        "What the system is — an internal maintainer console over one FastAPI backend "
        "(the production chat surface is the embeddable React widget)."
    )
    st.caption(
        "Unified operations dashboard for the Handyman project: "
        "classifier, RAG, chat, memory, widget, and observability in one place."
    )

    st.subheader("Try the production widget")
    st.markdown(
        "Streamlit is the internal AI Ops Control Center. The panel below embeds the "
        "external **host demo** page, which loads `/widget.js` and renders the production "
        "**React widget** as a bottom-right bubble — the same widget a real website would "
        "embed with the generated script tag. Click the bubble and send a message."
    )
    st.caption(
        "Both surfaces call the same FastAPI backend. Streamlit is for maintainers/admins; "
        "the widget is for end users / host-site visitors."
    )
    render_widget_preview(DEFAULT_WIDGET_ID, HOST_DEMO_URL, height=540)

    st.divider()

    st.subheader("What was built")
    st.markdown(
        "**Maintainer's Copilot** is an AI assistant for open-source maintainers. "
        "Given a GitHub issue, it classifies the issue type (bug/feature/docs/question), "
        "retrieves relevant documentation and past issues via hybrid RAG, "
        "answers questions using a hosted LLM, writes short- and long-term memory, "
        "and exposes an embeddable React chat widget for any web page. "
        "All components run as Docker services orchestrated by docker-compose."
    )

    st.subheader("Architecture")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "**Inference**\n"
            "- LogisticRegression TF-IDF — **served** (model_server)\n"
            "- CodeBERT — best by eval, **not served** (needs GPU)\n"
            "- Groq llama-3.3-70b (chat LLM)\n"
            "- E5 hybrid retrieval **served** (model_server /embed); TF-IDF fallback"
        )
    with col2:
        st.markdown(
            "**Infrastructure**\n"
            "- FastAPI REST API\n"
            "- PostgreSQL + pgvector\n"
            "- Redis (short-term memory)\n"
            "- MinIO (artifact storage)\n"
            "- Vault (secrets)\n"
            "- Jaeger (distributed tracing)"
        )
    with col3:
        st.markdown(
            "**UI**\n"
            "- Streamlit (this app — internal ops)\n"
            "- React widget (embeddable chat)\n"
            "- Host demo page (widget demo)\n"
            "- FastAPI docs (developer API ref)"
        )

    st.divider()

    st.subheader("Service links")
    links = [
        ("API docs", API_DOCS_URL),
        ("Streamlit app (this)", STREAMLIT_URL),
        ("Host demo (widget embed)", HOST_DEMO_URL),
        ("Widget app (React SPA)", WIDGET_APP_URL),
        ("Jaeger tracing", JAEGER_URL),
        ("MinIO console", MINIO_URL),
    ]
    cols = st.columns(3)
    for i, (label, url) in enumerate(links):
        cols[i % 3].markdown(f"[{label}]({url})")

    st.divider()

    st.subheader("Classifier metrics")
    st.caption(
        "Primary = CodeBERT fine-tuned. "
        "Fallback = LogisticRegression TF-IDF (no GPU, CI-safe, runtime default). "
        "Baseline = Ollama llama3 zero-shot."
    )
    render_classifier_metrics_table()

    st.divider()

    st.subheader("RAG retrieval metrics")
    st.caption(
        "Evaluated on 25-example golden set. Docker serves E5 hybrid (alpha=0.7) when "
        "model_server /embed is up; TF-IDF is the fallback (and CI gate). See Evaluation Defense."
    )
    render_rag_metrics_table()

    st.divider()

    st.subheader("Tech stack decisions")
    st.markdown(
        "| Decision | Choice | Reason |\n"
        "|---|---|---|\n"
        "| Classifier primary | CodeBERT | Best macro-F1 (0.7061) on kubernetes issues |\n"
        "| Classifier fallback | LR TF-IDF | No GPU, CI-safe, macro-F1 0.6938 |\n"
        "| Chat LLM | Groq llama-3.3-70b-versatile | Hosted, fast, no local GPU |\n"
        "| Secrets | HashiCorp Vault | Central secret management, production-grade |\n"
        "| Tracing | Jaeger (OpenTelemetry) | Distributed trace per request |\n"
        "| Artifact storage | MinIO | S3-compatible, self-hosted |\n"
        "| RAG retrieval | E5 hybrid α=0.7 served (TF-IDF fallback) | hit@5=0.68 (E5 hybrid) vs 0.40 (TF-IDF); UI shows retriever_used |"
    )
