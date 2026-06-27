"""Memory Inspector page — short-term (Redis) and long-term (Postgres) memory."""

from __future__ import annotations

import streamlit as st

import chatbot.api_client as client
from chatbot.components import page_proves


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
