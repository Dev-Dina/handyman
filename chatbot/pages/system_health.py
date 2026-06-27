"""System Health page — live API/model_server checks and service links."""

from __future__ import annotations

import streamlit as st

import chatbot.api_client as client
from chatbot.components import page_proves, status_badge
from chatbot.config import (
    API_DOCS_URL,
    HOST_DEMO_URL,
    JAEGER_URL,
    MINIO_URL,
    MODEL_SERVER_PUBLIC_URL,
    STREAMLIT_URL,
    WIDGET_APP_URL,
)


def page_system_health() -> None:
    st.title("System Health")
    page_proves(
        "The services are alive — live API + model_server checks, links for the rest."
    )
    st.caption(
        "Live checks for API and model_server. Other services validated by Docker healthcheck."
    )

    if st.button("Refresh health checks"):
        st.rerun()

    # Live HTTP checks
    st.subheader("Live HTTP checks")
    col1, col2 = st.columns(2)

    with col1:
        with st.spinner("Checking API..."):
            api_result = client.check_api_health()
        badge = status_badge(api_result["ok"])
        st.metric(label=f"{badge} API", value=api_result.get("status", "unknown"))
        st.caption(f"[Open API docs]({API_DOCS_URL})")

    with col2:
        with st.spinner("Checking model_server..."):
            ms_result = client.check_model_server_health()
        badge = status_badge(ms_result["ok"])
        st.metric(
            label=f"{badge} model_server", value=ms_result.get("status", "unknown")
        )
        st.caption(f"[model_server health]({MODEL_SERVER_PUBLIC_URL}/healthz)")

    st.divider()

    # Docker-healthchecked services
    st.subheader("Docker-healthchecked services")
    st.caption(
        "These services expose health endpoints only inside Docker networking. "
        "Status below reflects Docker healthcheck — open the links to verify."
    )

    rows = [
        ("Streamlit (this app)", STREAMLIT_URL, "Running — you are viewing this page"),
        ("Widget app (React)", WIDGET_APP_URL, "nginx serves /widget-app/"),
        ("Host demo page", HOST_DEMO_URL, "nginx serves embedded widget demo"),
        ("Jaeger tracing UI", JAEGER_URL, "jaegertracing/all-in-one:1.57"),
        ("MinIO console", MINIO_URL, "minio/minio — bucket browser"),
    ]
    for name, url, note in rows:
        col1, col2 = st.columns([2, 3])
        col1.markdown(f"[{name}]({url})")
        col2.caption(note)

    st.divider()

    # Infrastructure (DB, Redis, Vault)
    st.subheader("Infrastructure")
    st.info(
        "PostgreSQL, Redis, and Vault health is validated by Docker healthcheck "
        "(`pg_isready`, `redis-cli ping`, `vault status`). "
        "The API refuses to start unless all three are healthy via `depends_on`."
    )
    for svc, note in [
        (
            "PostgreSQL + pgvector",
            "pg16 + pgvector extension; migration 004 adds vector(384) + IVFFlat index",
        ),
        ("Redis", "Short-term memory store; 24h TTL per conversation"),
        ("HashiCorp Vault", "Dev mode; secrets at secret/handyman and secret/llm"),
    ]:
        st.markdown(f"- **{svc}**: {note}")
