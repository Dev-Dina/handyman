"""Page implementations for the AI Ops Control Center."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import chatbot.api_client as client
from chatbot.components import (
    lifecycle_badge,
    page_proves,
    render_rag_chunks,
    render_tool_call,
    render_widget_preview,
    status_badge,
)
from chatbot.config import (
    API_DOCS_URL,
    API_PUBLIC_URL,
    DEFAULT_WIDGET_ID,
    HOST_DEMO_URL,
    JAEGER_URL,
    MINIO_URL,
    MODEL_SERVER_PUBLIC_URL,
    STREAMLIT_URL,
    WIDGET_APP_URL,
)
from chatbot.state import new_conversation

# ── Constants ────────────────────────────────────────────────────────────────

_CLASSIFIER_METRICS = [
    ("CodeBERT (primary)", "0.7500", "0.7061", "PRIMARY"),
    ("LogisticRegression TF-IDF (fallback)", "0.7139", "0.6938", "FALLBACK"),
    ("Ollama llama3 (baseline)", "0.5850", "0.5554", "BASELINE"),
    ("CI LR golden (25 examples)", "0.7200", "0.6691", "CI gate"),
]

_RAG_METRICS = [
    ("E5 hybrid alpha=0.7 (served via /embed)", "0.68", "0.329"),
    ("TF-IDF (CI gate / fallback)", "0.40", "0.196"),
]

_JAEGER_SPANS = {
    "chat.request": "Entire chat request lifecycle",
    "llm.groq.chat": "Groq LLM API call (latency, token count)",
    "tool.rag_query": "RAG tool execution",
    "rag.retrieve": "Chunk retrieval step inside RAG",
    "tool.classify_issue": "Classifier tool execution",
    "tool.write_memory": "Memory write tool",
}

_MINIO_BUCKETS = ["handyman-artifacts", "handyman-evals"]

_ALL_TOOLS = [
    "rag_query",
    "classify_issue",
    "write_memory",
    "summarize",
    "extract_entities",
]

_RETRIEVER_OPTIONS = ["auto", "hybrid", "tfidf"]
_QUERY_TRANSFORM_OPTIONS = ["none", "technical_terms"]
_SOURCE_TYPE_OPTIONS = ["(any)", "doc", "issue", "comment"]

_ARTIFACT_MANIFEST = Path("reports/artifact_manifest.json")
_RAG_API_EVAL_REPORT = Path("reports/rag/api_eval_report.json")
_GENERATION_EVAL_REPORT = Path("reports/rag/generation_eval_report.json")

_EMBED_SNIPPET_TEMPLATE = (
    '<script src="{api_base}/widget.js"\n'
    '  data-widget-id="{widget_id}"\n'
    '  data-widget-url="{widget_app_url}"\n'
    '  data-api-base-url="{api_base}"></script>'
)


# ── 1. Overview ──────────────────────────────────────────────────────────────


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
    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown("**Model**")
    cols[1].markdown("**Accuracy**")
    cols[2].markdown("**Macro-F1**")
    cols[3].markdown("**Role**")
    for model, acc, f1, role in _CLASSIFIER_METRICS:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(model)
        cols[1].write(acc)
        cols[2].write(f1)
        cols[3].write(role)

    st.divider()

    st.subheader("RAG retrieval metrics")
    st.caption(
        "Evaluated on 25-example golden set. Docker serves E5 hybrid (alpha=0.7) when "
        "model_server /embed is up; TF-IDF is the fallback (and CI gate). See Evaluation Defense."
    )
    cols = st.columns([3, 1, 1])
    cols[0].markdown("**Pipeline**")
    cols[1].markdown("**Hit@5**")
    cols[2].markdown("**MRR@10**")
    for pipeline, h5, mrr in _RAG_METRICS:
        cols = st.columns([3, 1, 1])
        cols[0].write(pipeline)
        cols[1].write(h5)
        cols[2].write(mrr)

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


# ── 2. System Health ─────────────────────────────────────────────────────────


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


# ── 3. Chat Copilot ──────────────────────────────────────────────────────────


def page_chat() -> None:
    st.title("Chat Copilot")
    page_proves(
        "The internal maintainer tool-calling chat — Groq LLM orchestrating "
        "rag_query / classify_issue / write_memory, with structured tool-call cards."
    )
    st.info(
        "This is the **internal authenticated maintainer console**, not the production "
        "widget. The customer-facing surface is the embeddable React widget (see Widget Manager)."
    )

    token: str | None = st.session_state.access_token
    user: dict | None = st.session_state.user
    conv_id: str = st.session_state.conversation_id

    if not token:
        st.warning("Login required to use the Chat Copilot.")
        return

    # Controls row
    col1, col2 = st.columns([5, 1])
    with col1:
        st.caption(f"Conversation: `{conv_id}`")
    with col2:
        if st.button("New conversation", key="chat_new_conv"):
            new_conversation()

    # Tool toggles
    with st.expander("Tool toggles", expanded=False):
        st.caption("Select which tools the LLM may call on this turn.")
        tool_cols = st.columns(len(_ALL_TOOLS))
        tool_enabled: dict[str, bool] = {}
        for i, tool in enumerate(_ALL_TOOLS):
            default = tool in ("rag_query", "classify_issue")
            tool_enabled[tool] = tool_cols[i].checkbox(
                tool, value=default, key=f"tool_{tool}"
            )

    enabled = [t for t, on in tool_enabled.items() if on]

    # One-click demo prompts (use a fixed tool set so the demo always exercises tools)
    demo_prompt: str | None = None
    with st.expander("Demo prompts (one-click)", expanded=False):
        dcol1, dcol2 = st.columns(2)
        if dcol1.button("🔍 Use RAG to explain Kubernetes Services"):
            demo_prompt = (
                "Use the knowledge base to explain what Kubernetes Services are "
                "and how they expose Pods."
            )
        if dcol2.button("🏷️ Classify a CrashLoopBackOff issue"):
            demo_prompt = (
                "Classify this GitHub issue — Title: Pod stuck in CrashLoopBackOff. "
                "Body: kubelet reports back-off restarting failed container."
            )
        if dcol1.button("🧠 Remember a maintainer preference"):
            demo_prompt = (
                "Remember that this maintainer prefers concise, evidence-first "
                "issue triage answers."
            )
        if dcol2.button("⚠️ Ask a weak-retrieval question (honest answer)"):
            demo_prompt = "Why is kubernetes not loading?"
    _DEMO_TOOLS = ["rag_query", "classify_issue", "write_memory"]

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Tool calls from last turn
    if st.session_state.tool_calls:
        with st.expander("Tool calls from last turn"):
            for tc in st.session_state.tool_calls:
                render_tool_call(tc)

    # Trace + conversation info
    if st.session_state.trace_id:
        tcol1, tcol2 = st.columns([3, 1])
        tcol1.caption(f"Trace: `{st.session_state.trace_id}`")
        tcol2.markdown(f"[Open in Jaeger]({JAEGER_URL})")

    # Input — chat box or a one-click demo prompt
    prompt = st.chat_input("Ask about Kubernetes issues...") or demo_prompt
    if prompt:
        call_tools = _DEMO_TOOLS if demo_prompt else (enabled if enabled else None)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = client.chat(
                    prompt,
                    conversation_id=conv_id,
                    user_id=str(user["id"]) if user else None,
                    token=token,
                    enabled_tools=call_tools,
                )

            if "error" in result:
                st.error(result["error"])
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"[Error] {result['error']}"}
                )
            else:
                answer = result.get("answer", "")
                st.write(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
                st.session_state.tool_calls = result.get("tool_calls", [])
                st.session_state.trace_id = result.get("trace_id")
                if result.get("conversation_id"):
                    st.session_state.conversation_id = result["conversation_id"]

                if result.get("tool_calls"):
                    with st.expander("Tool calls this turn", expanded=True):
                        for tc in result["tool_calls"]:
                            render_tool_call(tc)

                meta_parts = []
                if result.get("trace_id"):
                    meta_parts.append(f"Trace: `{result['trace_id']}`")
                if result.get("model"):
                    meta_parts.append(f"Model: `{result['model']}`")
                if result.get("latency_seconds") is not None:
                    meta_parts.append(f"Latency: `{result['latency_seconds']:.2f}s`")
                if meta_parts:
                    st.caption(" · ".join(meta_parts))


# ── 4. RAG Explorer ──────────────────────────────────────────────────────────


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
        retriever = col2.selectbox("Retriever", _RETRIEVER_OPTIONS, index=0)
        query_transform = col3.selectbox(
            "Query transform", _QUERY_TRANSFORM_OPTIONS, index=0
        )
        source_raw = st.selectbox("Source type filter", _SOURCE_TYPE_OPTIONS, index=0)
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


# ── 5. Classifier Playground ─────────────────────────────────────────────────


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
    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown("**Model**")
    cols[1].markdown("**Accuracy**")
    cols[2].markdown("**Macro-F1**")
    cols[3].markdown("**Role**")
    for model, acc, f1, role in _CLASSIFIER_METRICS:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(model)
        cols[1].write(acc)
        cols[2].write(f1)
        cols[3].write(role)


# ── 6. Memory Inspector ──────────────────────────────────────────────────────


def page_memory() -> None:
    st.title("Memory Inspector")
    page_proves(
        "Memory is real — short-term in Redis (24h TTL) and long-term in Postgres."
    )

    conv_id: str | None = st.session_state.conversation_id
    token: str | None = st.session_state.access_token

    if not token:
        st.warning("Login required to inspect memory.")
        return

    if not conv_id:
        st.info("No active conversation. Start a chat first.")
        return

    st.write(f"Conversation: `{conv_id}`")
    if st.button("Refresh"):
        st.rerun()

    # Short-term
    st.subheader("Short-term memory (Redis)")
    st.caption(
        "TTL: 24 hours per conversation. Stores recent messages for context window."
    )
    result_st = client.get_short_term_memory(conv_id, token)
    if "error" in result_st:
        st.warning(f"Short-term memory unavailable: {result_st['error']}")
        st.caption(
            "Check that Redis is running and REDIS_URL is set correctly in docker-compose."
        )
    else:
        items = result_st.get("items", [])
        if not items:
            st.info("No short-term memory items for this conversation.")
        else:
            st.metric("Items", len(items))
            for item in items:
                preview = str(item.get("content", ""))[:80]
                role = item.get("role", "?")
                with st.expander(f"[{role}] {preview}"):
                    st.json(item)

    st.divider()

    # Long-term
    st.subheader("Long-term memory (Postgres)")
    st.caption("Episodic memory. Stored after conversations via write_memory tool.")
    result_lt = client.get_long_term_memories(token, conversation_id=conv_id)
    if "error" in result_lt:
        st.warning(f"Long-term memory unavailable: {result_lt['error']}")
    else:
        memories = result_lt.get("items", [])
        if not memories:
            st.info("No long-term memories for this conversation.")
        else:
            st.metric("Memories", len(memories))
            for mem in memories:
                preview = str(mem.get("content", ""))[:80]
                mem_type = mem.get("memory_type", "?")
                with st.expander(f"[{mem_type}] {preview}"):
                    st.json(mem)


# ── 7. Widget Manager ────────────────────────────────────────────────────────


def page_widget_manager() -> None:
    st.title("Widget Manager")
    page_proves(
        "Configure the production embed — the React widget is the customer-facing surface; "
        "Streamlit only manages its config."
    )
    st.caption(
        "This Streamlit app is the internal AI Ops Control Center. The production "
        "chat surface is the embeddable React widget configured here — it renders as a "
        "bottom-right bubble on any host page via the `/widget.js` loader."
    )
    st.info(
        "**Allowed origins** must include `http://localhost:3000` (the widget iframe "
        "fetches its config from this origin) and `http://localhost:8080` (the host demo "
        "page, allowed to frame the widget). The host page loads the widget through the "
        "generated `<script>` snippet — not by opening the widget app directly."
    )
    st.markdown(
        f"{lifecycle_badge('deployed')} **React widget** = production embedded chat "
        "(bottom-right bubble on the host demo). This page only configures it."
    )

    token: str | None = st.session_state.access_token
    user: dict | None = st.session_state.user

    if not token or not user:
        st.warning("Login required.")
        return

    is_admin = user.get("role") == "admin"

    if not is_admin:
        st.warning("Admin access required to manage widget configurations.")
        st.caption(f"Your role: `{user.get('role', 'unknown')}`")
        st.info("Ask an admin to create a widget config and share the embed snippet.")
        return

    # Existing widgets
    st.subheader("Existing widgets")
    if st.button("Refresh widget list"):
        st.rerun()

    list_result = client.list_widgets(token)
    if "error" in list_result:
        st.error(f"Could not list widgets: {list_result['error']}")
    else:
        widgets = list_result.get("items", [])
        if not widgets:
            st.info("No widget configs found. Create one below.")
        else:
            for w in widgets:
                pub_id = w.get("public_widget_id", "")
                with st.expander(f"Widget `{pub_id}`"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**Active**: {w.get('is_active', '?')}")
                    col2.write(f"**Greeting**: {w.get('greeting', '—')}")
                    st.write(f"**Allowed origins**: {w.get('allowed_origins', [])}")
                    st.write(f"**Enabled tools**: {w.get('enabled_tools', [])}")
                    snippet = _EMBED_SNIPPET_TEMPLATE.format(
                        api_base=API_PUBLIC_URL,
                        widget_id=pub_id,
                        widget_app_url=WIDGET_APP_URL,
                    )
                    st.subheader("Embed snippet")
                    st.code(snippet, language="html")
                    st.caption(f"[Open host demo]({HOST_DEMO_URL})")
                    # Preview this widget here (button-gated so only one iframe loads).
                    if st.checkbox(
                        "Preview this widget here", key=f"preview_{pub_id}"
                    ):
                        render_widget_preview(pub_id, HOST_DEMO_URL, height=520)

    st.divider()

    # Create new widget
    st.subheader("Create widget config")
    with st.form("create_widget_form"):
        origins_raw = st.text_input(
            "Allowed origins (comma-separated)",
            value="http://localhost:3000,http://localhost:8080",
            help="Origins that may embed this widget. Must start with http:// or https://.",
        )
        greeting = st.text_input(
            "Greeting message", value="Hi! How can I help you today?"
        )
        tools_raw = st.multiselect(
            "Enabled tools",
            options=_ALL_TOOLS,
            default=["rag_query", "classify_issue"],
        )
        primary_color = st.color_picker("Theme primary color", value="#2563eb")
        position = st.selectbox(
            "Widget position", ["bottom-right", "bottom-left"], index=0
        )
        is_active = st.checkbox("Active", value=True)
        submitted = st.form_submit_button("Create widget")

    if not submitted:
        return

    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    if not origins:
        st.error("At least one allowed origin is required.")
        return

    theme = {"primary_color": primary_color, "position": position}

    with st.spinner("Creating widget..."):
        result = client.create_widget(
            token,
            allowed_origins=origins,
            greeting=greeting,
            enabled_tools=tools_raw,
            theme=theme,
            is_active=is_active,
        )

    if "error" in result:
        st.error(f"Create failed: {result['error']}")
        return

    pub_id = result.get("public_widget_id", "")
    st.success(f"Widget created! `public_widget_id = {pub_id}`")

    snippet = _EMBED_SNIPPET_TEMPLATE.format(
        api_base=API_PUBLIC_URL,
        widget_id=pub_id,
        widget_app_url=WIDGET_APP_URL,
    )
    st.subheader("Your embed snippet")
    st.code(snippet, language="html")
    st.caption(
        f"For the bundled demo, just open the host page with this id — no rebuild needed: "
        f"`{HOST_DEMO_URL}/?widget_id={pub_id}` (the id is remembered in the browser). "
        f"Ensure this widget's allowed origins include `http://localhost:3000` and "
        f"`http://localhost:8080`."
    )
    st.markdown(
        f"[Open host demo with this widget]({HOST_DEMO_URL}/?widget_id={pub_id})"
    )


# ── 8. Observability ─────────────────────────────────────────────────────────


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
    for span, description in _JAEGER_SPANS.items():
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


# ── 9. Artifacts / MinIO ─────────────────────────────────────────────────────


def page_artifacts() -> None:
    st.title("Artifacts / MinIO")
    page_proves(
        "The artifact/blob story — S3-compatible MinIO for models, eval reports, snapshots."
    )
    st.caption(
        "MinIO is the S3-compatible artifact store. Eval reports, retrieval snapshots, and model artifacts are uploaded here."
    )

    col1, col2 = st.columns([2, 1])
    col1.metric("MinIO console", MINIO_URL)
    col2.markdown(f"[Open MinIO]({MINIO_URL})")

    st.subheader("Expected buckets")
    for bucket in _MINIO_BUCKETS:
        st.markdown(f"- `{bucket}`")

    st.subheader("What MinIO stores")
    st.markdown(
        "| Bucket | Contents |\n"
        "|---|---|\n"
        "| `handyman-artifacts` | Classifier model artifacts, eval reports, training summaries |\n"
        "| `handyman-evals` | RAG retrieval snapshots, golden eval outputs, RAGAS reports |"
    )

    st.divider()

    st.subheader("Artifact manifest")
    if _ARTIFACT_MANIFEST.exists():
        try:
            manifest = json.loads(_ARTIFACT_MANIFEST.read_text())
            st.success(f"Loaded `{_ARTIFACT_MANIFEST}` — {len(manifest)} entries")
            with st.expander("View manifest"):
                st.json(manifest)
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Could not parse manifest: {exc}")
    else:
        st.info(
            f"`{_ARTIFACT_MANIFEST}` is not present in the running container. "
            "This file is a repo-side artifact generated by `scripts/audit_reports.py`. "
            "It is not packaged into the Docker image. "
            "To view it: run `python scripts/audit_reports.py` locally, "
            "then open the generated `reports/artifact_manifest.json`."
        )

    st.divider()

    st.subheader("Default credentials (local dev)")
    st.caption("These match the docker-compose.yml defaults. Change for production.")
    st.code(
        "MINIO_ROOT_USER=minioadmin\nMINIO_ROOT_PASSWORD=minioadmin",
        language="bash",
    )


# ── 11. Evaluation Defense ───────────────────────────────────────────────────


def page_eval_defense() -> None:
    st.title("Evaluation Defense")
    page_proves(
        "The deployed-vs-offline truth — what is actually served, the real metrics, "
        "and the honest eval gaps."
    )
    st.caption(
        "Honest account of what is evaluated vs what is served. No metric here is "
        "invented; unimplemented evals are shown as gaps, not numbers."
    )

    gen_present = _GENERATION_EVAL_REPORT.exists()
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)
    bcol1.metric("Classifier", lifecycle_badge("deployed"), "LR TF-IDF")
    bcol2.metric("CodeBERT", lifecycle_badge("offline"), "primary by eval")
    bcol3.metric("RAG hybrid (E5)", lifecycle_badge("deployed"), "served via /embed")
    bcol4.metric(
        "Generation eval",
        lifecycle_badge("deployed" if gen_present else "gap"),
        "deterministic proxy" if gen_present else "not implemented",
    )

    with st.expander("Live eval summary (served by the API — no chatbot rebuild needed)"):
        summary = client.get_eval_summary()
        if "error" in summary:
            st.caption(f"API eval summary unavailable: {summary['error']}")
        else:
            rag_sum = summary.get("rag_retrieval", {})
            st.caption(
                f"hybrid artifact present: `{rag_sum.get('hybrid_artifact_present')}` · "
                f"offline E5 hybrid: hit@5=`{rag_sum.get('offline_best_e5_hybrid', {}).get('hit_at_5')}`"
            )
            st.json(summary)

    st.subheader("Served vs evaluated")
    st.markdown(
        "| Capability | Best by evaluation | Served at runtime (Docker) |\n"
        "|---|---|---|\n"
        "| Issue classifier | CodeBERT (macro-F1 0.7061) | **LogisticRegression TF-IDF** (GPU-free, CI-safe) |\n"
        "| RAG retrieval | E5 hybrid α=0.7 (hit@5 0.68) | **E5 hybrid served** via model_server /embed; TF-IDF fallback (hit@5 ≈ 0.40) |"
    )
    st.info(
        "CodeBERT is **primary by evaluation, not Docker-served** (it needs torch/GPU). "
        "**E5 hybrid retrieval is now served in Docker**: model_server exposes a CPU "
        "`/embed` endpoint (transformers, mean-pool + L2) and the E5 chunk embeddings ship "
        "in the API image (`artifacts/rag/`). Live `/api/v1/rag/query` returns "
        "`retriever_used=hybrid`; it falls back to TF-IDF if `/embed` or the artifact is "
        "unavailable. Torch lives only in the model_server image."
    )

    st.divider()
    st.subheader("Classifier metrics (official)")
    cols = st.columns([3, 1, 1, 1])
    cols[0].markdown("**Model**")
    cols[1].markdown("**Accuracy**")
    cols[2].markdown("**Macro-F1**")
    cols[3].markdown("**Role**")
    for model, acc, f1, role in _CLASSIFIER_METRICS:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(model)
        cols[1].write(acc)
        cols[2].write(f1)
        cols[3].write(role)

    st.divider()
    st.subheader("RAG retrieval metrics")
    cols = st.columns([3, 1, 1])
    cols[0].markdown("**Pipeline**")
    cols[1].markdown("**Hit@5**")
    cols[2].markdown("**MRR@10**")
    for pipeline, h5, mrr in _RAG_METRICS:
        cols = st.columns([3, 1, 1])
        cols[0].write(pipeline)
        cols[1].write(h5)
        cols[2].write(mrr)
    st.caption(
        "Deployed runtime serves **E5 hybrid** (`retriever_used=hybrid`, verified live) "
        "when model_server `/embed` + the shipped E5 chunk embeddings are present; "
        "otherwise it transparently falls back to `tfidf_fallback`."
    )
    if _RAG_API_EVAL_REPORT.exists():
        try:
            rep = json.loads(_RAG_API_EVAL_REPORT.read_text())
            st.caption(
                f"Latest CI eval ({_RAG_API_EVAL_REPORT}): "
                f"mode=`{rep.get('retrieval_mode', '?')}` · "
                f"hit@5=`{rep.get('hit_at_5', '?')}` · "
                f"mrr@10=`{rep.get('mrr_at_10', '?')}` · "
                f"n=`{rep.get('n_questions', '?')}`"
            )
        except Exception as exc:  # noqa: BLE001
            st.caption(f"Could not parse RAG eval report: {exc}")

    st.divider()
    st.subheader("Generation eval (faithfulness / answer relevancy)")
    gen = None
    if _GENERATION_EVAL_REPORT.exists():
        try:
            gen = json.loads(_GENERATION_EVAL_REPORT.read_text())
        except Exception as exc:  # noqa: BLE001
            st.warning(f"Could not parse generation eval report: {exc}")
    if gen:
        st.caption(
            f"Deterministic CI-safe proxy ({lifecycle_badge('deployed')}) · "
            f"judge=`{gen.get('judge', 'none')}` · "
            f"rows={gen.get('rows_evaluated', '?')} · "
            f"scope=`{gen.get('scope', '?')}`"
        )
        g1, g2, g3 = st.columns(3)
        g1.metric("Faithfulness (proxy)", gen.get("faithfulness_proxy_mean", "—"))
        g2.metric("Answer relevancy (proxy)", gen.get("answer_relevancy_proxy_mean", "—"))
        g3.metric("Unsupported claims (proxy)", gen.get("unsupported_claims_proxy_mean", "—"))
        h1, h2 = st.columns(2)
        h1.metric("Retrieved-context overlap", gen.get("retrieved_context_overlap_mean", "—"))
        h2.metric("Ideal-answer overlap", gen.get("ideal_answer_overlap_mean", "—"))
        with st.expander("Limitations of this proxy"):
            for lim in gen.get("limitations", []):
                st.markdown(f"- {lim}")
        with st.expander("Per-row detail"):
            st.json(gen.get("items", []))
    else:
        st.warning(
            f"{lifecycle_badge('gap')} **Generation eval report not found in this "
            "container.** Generate it with `python -m pipelines.rag.eval_generation` "
            "and rebuild the chatbot image. The golden set carries `ideal_answer` and "
            "`hand_labeled_for_judge_check` for a deterministic (token-overlap) proxy, "
            "with an opt-in LLM judge. Retrieval eval (hit@5 / mrr@10) above is gated in CI."
        )

    st.divider()
    st.subheader("How to defend this")
    st.markdown(
        "- **Deployment is a deliberate trade-off, not a shortcut.** CodeBERT wins on "
        "macro-F1 (0.7061) but needs GPU/torch; we serve LogisticRegression TF-IDF "
        "(0.6938) so the demo is GPU-free, fast, and CI-safe — a −0.012 macro-F1 cost.\n"
        "- **RAG serves E5 hybrid live, and is honest about it.** `retriever_used` reads "
        "`hybrid` when model_server `/embed` + the shipped E5 chunk embeddings are present "
        "(hit@5 0.68 offline-measured), and transparently falls back to `tfidf_fallback` "
        "otherwise — the field always reflects what actually ran.\n"
        "- **Metrics are reproducible.** `pipelines.classifier.eval_golden` and "
        "`pipelines.rag.eval_api` regenerate the gated numbers; thresholds live in "
        "`eval_thresholds.yaml`.\n"
        "- **Generation quality has a deterministic proxy.** Faithfulness / answer "
        "relevancy are scored by reproducible token-overlap over the 5 hand-labeled "
        "golden rows (`pipelines.rag.eval_generation`) — CI-safe, no API key. It is a "
        "proxy, not a semantic LLM judge; an LLM-as-judge remains optional/manual. We "
        "never fabricate scores."
    )


# ── 10. Demo Runbook ──────────────────────────────────────────────────────────


def page_demo_runbook() -> None:
    st.title("Demo Runbook")
    page_proves(
        "The final walkthrough — exact steps to present the whole system end-to-end."
    )
    st.caption(
        "Step-by-step guide for a live presentation or walkthrough of the full system."
    )

    st.subheader("Prerequisites")
    st.code(
        "cp .env.example .env\n"
        "# Add your Groq key:\n"
        "docker compose up --build -d\n"
        'docker compose exec vault vault kv put secret/llm groq_api_key="gsk_your_key"',
        language="bash",
    )

    steps = [
        (
            "1. Verify all services healthy",
            "Open [System Health](?nav=System+Health) — API and model_server should show ✅.\n\n"
            "Or from terminal:\n"
            "```bash\n"
            "docker compose ps\n"
            "curl http://localhost:8000/healthz\n"
            "curl http://localhost:8001/healthz\n"
            "```",
        ),
        (
            "2. Register + login",
            "```bash\n"
            "curl -X POST http://localhost:8000/api/v1/auth/register \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"email":"demo@example.com","password":"demo-password-123","role":"admin"}\'\n'
            "```\n"
            "Then login in this Streamlit app (left sidebar form).",
        ),
        (
            "3. Test RAG Explorer",
            "Go to **RAG Explorer**. Enter:\n"
            "- Question: `How do I configure a PodDisruptionBudget?`\n"
            "- Retriever: `hybrid`\n"
            "- Query transform: `technical_terms`\n\n"
            "Expected: extractive answer + ranked chunks with source_type and scores.",
        ),
        (
            "4. Test Classifier Playground",
            "Go to **Classifier Playground**. Enter:\n"
            "- Title: `Pod OOMKilled after node restart`\n"
            "- Body: `Steps to reproduce: upgrade node pool, pod gets OOMKilled`\n\n"
            "Expected: label=`bug`, confidence > 0.5, model=`lr_tfidf_fallback`.",
        ),
        (
            "5. Test Chat Copilot with tools",
            "Go to **Chat Copilot**. Enable tools: `rag_query`, `classify_issue`, `write_memory`.\n\n"
            "Send: `Classify this issue and find relevant docs: Pod OOMKilled after upgrade`\n\n"
            "Expected: LLM calls rag_query + classify_issue tools, returns structured answer, "
            "trace_id appears below response.",
        ),
        (
            "6. Check Memory Inspector",
            "Go to **Memory Inspector**. "
            "Short-term memory should show the messages from the previous chat. "
            "Long-term memory appears if write_memory was called.",
        ),
        (
            "7. Open Jaeger trace",
            f"Go to **Observability** — copy the last `trace_id`. "
            f"Open [{JAEGER_URL}]({JAEGER_URL}), select service `handyman`, "
            "paste the trace_id. See the full span waterfall.",
        ),
        (
            "8. Create a widget config (admin)",
            "Go to **Widget Manager** (admin required). "
            "Create a config with `allowed_origins: http://localhost:3000,http://localhost:8080`. "
            "Copy the `public_widget_id` from the result.",
        ),
        (
            "9. Open host demo widget",
            f"Open [{HOST_DEMO_URL}]({HOST_DEMO_URL}). "
            "A floating chat bubble should appear in the bottom-right corner. "
            "Click it — the widget expands. Send a message.\n\n"
            "If the bubble does not appear, update `demo/host/index.html` "
            "with the `public_widget_id` from step 8 and rebuild: "
            "`docker compose build host && docker compose up -d host`.",
        ),
        (
            "10. Check MinIO artifacts",
            f"Open [{MINIO_URL}]({MINIO_URL}) (minioadmin / minioadmin). "
            "Browse `handyman-artifacts` and `handyman-evals` buckets. "
            "Eval reports are uploaded by pipelines/rag/eval_api.py and the classifier eval pipeline.",
        ),
    ]

    for title, body in steps:
        with st.expander(title, expanded=False):
            st.markdown(body)

    st.divider()

    st.subheader("Official metrics summary")
    st.markdown(
        "| Track | Metric | Value |\n"
        "|---|---|---|\n"
        "| Classifier primary | CodeBERT macro-F1 | **0.7061** |\n"
        "| Classifier fallback | LR TF-IDF macro-F1 | **0.6938** |\n"
        "| Classifier baseline | Ollama llama3 macro-F1 | 0.5554 |\n"
        "| RAG (deployed) | E5 hybrid hit@5 | **0.68** |\n"
        "| RAG (deployed) | E5 hybrid MRR@10 | **0.329** |\n"
        "| RAG (CI baseline) | TF-IDF hit@5 | 0.40 |"
    )
