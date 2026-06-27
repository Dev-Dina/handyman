"""Observability page — Jaeger trace reference and structured-log guidance."""

from __future__ import annotations

import streamlit as st

from chatbot.components import page_proves
from chatbot.config import JAEGER_URL
from chatbot.pages._shared import JAEGER_SPANS


def page_observability() -> None:
    st.title("Observability")
    page_proves(
        "Real chat/tool calls are traced — span waterfall per request in Jaeger."
    )
    st.caption(
        "Distributed tracing via Jaeger (OpenTelemetry). Every chat request produces a trace."
    )

    trace_id = st.session_state.get("trace_id")

    col1, col2 = st.columns([3, 1])
    col1.metric(
        "Last trace_id (this session)",
        trace_id if trace_id else "none yet",
    )
    col2.markdown(f"[Open Jaeger]({JAEGER_URL})")

    if trace_id:
        st.info(
            f"To find this trace in Jaeger: open {JAEGER_URL}, "
            f"select service `handyman`, search by Trace ID `{trace_id}`."
        )

    st.divider()

    st.subheader("Trace span reference")
    st.caption(
        "Each span below corresponds to a named OpenTelemetry span in the codebase."
    )
    for span, description in JAEGER_SPANS.items():
        col1, col2 = st.columns([2, 3])
        col1.code(span)
        col2.write(description)

    st.divider()

    st.subheader("How to search a trace in Jaeger")
    st.markdown(
        f"1. Open [{JAEGER_URL}]({JAEGER_URL})\n"
        "2. Select **Service**: `handyman`\n"
        "3. Select **Operation**: `chat.request` (or any span)\n"
        "4. Click **Find Traces** — recent traces appear below\n"
        "5. To find a specific trace: paste the `trace_id` into the **Trace ID** field\n"
        "6. Click a trace to see the full span waterfall: "
        "`chat.request → llm.groq.chat → tool.rag_query → rag.retrieve`"
    )

    st.divider()

    st.subheader("Structured logs")
    st.markdown(
        "Every log line is JSON-structured with `request_id`, `trace_id`, and redacted values. "
        "View logs with:\n"
        "```bash\n"
        "docker compose logs api --follow\n"
        "docker compose logs model_server --follow\n"
        "```"
    )
