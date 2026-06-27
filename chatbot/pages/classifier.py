"""Classifier Playground page — runtime classify_issue tool path."""

from __future__ import annotations

import json

import streamlit as st

import chatbot.api_client as client
from chatbot.components import page_proves, render_tool_call
from chatbot.config import JAEGER_URL
from chatbot.pages._shared import render_classifier_metrics_table


def page_classifier() -> None:
    st.title("Classifier Playground")
    page_proves(
        "The runtime classifier path — chat → classify_issue tool → model_server "
        "(LogisticRegression TF-IDF), with the official model comparison."
    )
    st.caption(
        "Classify a GitHub issue into bug / feature / docs / question. "
        "Uses the chat API with classify_issue tool (runtime: LogisticRegression TF-IDF fallback)."
    )

    with st.form("classify_form"):
        title = st.text_input(
            "Issue title", placeholder="Pod fails to start after node restart"
        )
        body = st.text_area(
            "Issue body",
            placeholder="Steps to reproduce: ...",
            height=120,
        )
        submitted = st.form_submit_button("Classify")

    if not submitted:
        _show_classifier_metrics()
        return

    if not title.strip():
        st.warning("Enter an issue title.")
        _show_classifier_metrics()
        return

    token: str | None = st.session_state.get("access_token")
    if not token:
        st.warning("Login required — the classify_issue tool requires auth.")
        _show_classifier_metrics()
        return

    issue_text = (
        f"Title: {title}\n\nBody: {body}" if body.strip() else f"Title: {title}"
    )
    conv_id: str = st.session_state.get("conversation_id", "")

    with st.spinner("Classifying..."):
        result = client.chat(
            issue_text,
            conversation_id=conv_id,
            user_id=str(st.session_state.user["id"])
            if st.session_state.get("user")
            else None,
            token=token,
            enabled_tools=["classify_issue"],
        )

    if "error" in result:
        st.error(result["error"])
        _show_classifier_metrics()
        return

    # Parse tool call result
    tool_calls = result.get("tool_calls", [])
    classification: dict = {}
    for tc in tool_calls:
        if tc.get("tool_name") == "classify_issue" or "label" in str(
            tc.get("result", {})
        ):
            raw = tc.get("result", {})
            if isinstance(raw, dict):
                classification = raw
            elif isinstance(raw, str):
                try:
                    classification = json.loads(raw)
                except Exception:  # noqa: BLE001
                    pass
            break

    st.subheader("Classification result")
    if classification:
        col1, col2, col3 = st.columns(3)
        col1.metric("Label", classification.get("label", "—"))
        conf = classification.get("confidence") or classification.get("score")
        col2.metric("Confidence", f"{conf:.3f}" if conf is not None else "—")
        col3.metric("Model", classification.get("model", "lr_tfidf_fallback"))
    else:
        st.info(
            "No structured classification extracted. See LLM answer and raw tool calls below."
        )

    st.subheader("LLM answer")
    st.write(result.get("answer", ""))

    if tool_calls:
        with st.expander("Tool calls"):
            for tc in tool_calls:
                render_tool_call(tc)

    if result.get("trace_id"):
        st.caption(f"Trace: `{result['trace_id']}` · [Open in Jaeger]({JAEGER_URL})")

    st.info(
        "**Runtime model**: LogisticRegression TF-IDF (operational fallback). "
        "CodeBERT is the primary model but requires GPU inference via model_server. "
        "The chat tool uses the TF-IDF fallback for CI-safe classification."
    )

    _show_classifier_metrics()


def _show_classifier_metrics() -> None:
    st.divider()
    st.subheader("Official classifier comparison")
    render_classifier_metrics_table()
