"""RAG Explorer page — retrieval in isolation from the LLM."""

from __future__ import annotations

import streamlit as st

import chatbot.api_client as client
from chatbot.components import page_proves, render_rag_chunks
from chatbot.pages._shared import (
    QUERY_TRANSFORM_OPTIONS,
    RETRIEVER_OPTIONS,
    SOURCE_TYPE_OPTIONS,
)


def page_rag_explorer() -> None:
    st.title("RAG Explorer")
    page_proves(
        "Retrieval in isolation from the LLM — see exactly which chunks rank and why."
    )
    st.caption(
        "Run retrieval independently from LLM generation. "
        "Uses POST /api/v1/rag/query — same pipeline as the chat rag_query tool."
    )

    with st.form("rag_form"):
        question = st.text_input(
            "Question",
            placeholder="How do I configure a Kubernetes PodDisruptionBudget?",
        )
        col1, col2, col3 = st.columns(3)
        top_k = col1.number_input("top_k", min_value=1, max_value=20, value=5)
        retriever = col2.selectbox("Retriever", RETRIEVER_OPTIONS, index=0)
        query_transform = col3.selectbox(
            "Query transform", QUERY_TRANSFORM_OPTIONS, index=0
        )
        source_raw = st.selectbox("Source type filter", SOURCE_TYPE_OPTIONS, index=0)
        maintainer_only = st.checkbox("Maintainer-only chunks", value=False)
        submitted = st.form_submit_button("Retrieve")

    if not submitted:
        return
    if not question.strip():
        st.warning("Enter a question.")
        return

    source_type = None if source_raw == "(any)" else source_raw
    token: str | None = st.session_state.get("access_token")

    with st.spinner("Retrieving..."):
        result = client.rag_query(
            question,
            top_k=int(top_k),
            retriever=retriever,
            query_transform=query_transform,
            source_type=source_type,
            maintainer_only=maintainer_only,
            token=token,
        )

    if "error" in result:
        st.error(result["error"])
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Latency", f"{result.get('latency_seconds', 0):.3f}s")
    col2.metric("Retriever used", result.get("retriever_used", "—"))
    col3.metric("Chunks returned", len(result.get("results", [])))

    if result.get("answer"):
        st.subheader("Extractive answer")
        st.info(result["answer"])

    chunks = result.get("results", [])
    if chunks:
        st.subheader(f"Retrieved chunks ({len(chunks)})")
        render_rag_chunks(chunks)
    else:
        st.info("No chunks returned.")
