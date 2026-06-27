"""Chat Copilot page — internal maintainer tool-calling chat."""

from __future__ import annotations

import streamlit as st

import chatbot.api_client as client
from chatbot.components import page_proves, render_tool_call
from chatbot.config import JAEGER_URL
from chatbot.pages._shared import ALL_TOOLS
from chatbot.state import new_conversation


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
        tool_cols = st.columns(len(ALL_TOOLS))
        tool_enabled: dict[str, bool] = {}
        for i, tool in enumerate(ALL_TOOLS):
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
