"""Maintainer's Copilot — authenticated internal Streamlit app.

Calls the FastAPI backend over HTTP. JWT stored in st.session_state only.
No direct DB, Redis, or Vault access. No business logic duplicated here.
"""

from __future__ import annotations

import uuid

import streamlit as st

from chatbot.api_client import (
    chat,
    get_long_term_memories,
    get_short_term_memory,
    login,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_DEFAULT_STATE: dict = {
    "logged_in": False,
    "access_token": None,
    "user": None,
    "conversation_id": None,
    "messages": [],
    "tool_calls": [],
    "trace_id": None,
}


def _init_state() -> None:
    for key, default in _DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _logout() -> None:
    for key in _DEFAULT_STATE:
        st.session_state[key] = _DEFAULT_STATE[key]
    st.rerun()


def _new_conversation() -> None:
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.tool_calls = []
    st.session_state.trace_id = None
    st.rerun()


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------


def _login_page() -> None:
    st.title("Maintainer's Copilot")
    st.subheader("Sign In")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
            return
        result = login(email, password)
        if "error" in result:
            st.error(result["error"])
        else:
            st.session_state.logged_in = True
            st.session_state.access_token = result["access_token"]
            st.session_state.user = result["user"]
            st.session_state.conversation_id = str(uuid.uuid4())
            st.rerun()


# ---------------------------------------------------------------------------
# Chat page
# ---------------------------------------------------------------------------


def _chat_page() -> None:
    st.header("Chat")

    conv_id: str = st.session_state.conversation_id
    user: dict | None = st.session_state.user
    token: str | None = st.session_state.access_token

    col1, col2 = st.columns([5, 1])
    with col1:
        st.caption(f"Conversation: `{conv_id}`")
    with col2:
        if st.button("New conversation", key="new_conv_btn"):
            _new_conversation()

    # Display conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Display tool calls from last turn
    if st.session_state.tool_calls:
        with st.expander("Tool calls from last turn"):
            for tc in st.session_state.tool_calls:
                st.json(tc)

    # Display trace_id from last turn
    if st.session_state.trace_id:
        st.caption(f"Trace: `{st.session_state.trace_id}`")

    # Chat input — triggers rerun on submit
    if prompt := st.chat_input("Ask about Kubernetes issues..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = chat(
                    prompt,
                    conversation_id=conv_id,
                    user_id=str(user["id"]) if user else None,
                    token=token,
                )

            if "error" in result:
                error_msg = result["error"]
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": f"[Error] {error_msg}"}
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
                    with st.expander("Tool calls this turn"):
                        for tc in result["tool_calls"]:
                            st.json(tc)
                if result.get("trace_id"):
                    st.caption(f"Trace: `{result['trace_id']}`")


# ---------------------------------------------------------------------------
# Memory inspector page
# ---------------------------------------------------------------------------


def _memory_page() -> None:
    st.header("Memory Inspector")

    conv_id: str | None = st.session_state.conversation_id
    token: str | None = st.session_state.access_token

    if not conv_id:
        st.info("No active conversation. Start a chat first.")
        return

    st.write(f"Conversation: `{conv_id}`")

    if st.button("Refresh"):
        st.rerun()

    # Short-term memory
    st.subheader("Short-term memory (Redis)")
    if token:
        result_st = get_short_term_memory(conv_id, token)
        if "error" in result_st:
            st.warning(f"Short-term memory unavailable: {result_st['error']}")
        else:
            items = result_st.get("items", [])
            if not items:
                st.info("No short-term memory items for this conversation.")
            else:
                for item in items:
                    preview = str(item.get("content", ""))[:80]
                    role = item.get("role", "?")
                    with st.expander(f"[{role}] {preview}"):
                        st.json(item)
    else:
        st.warning("Not logged in — cannot fetch memory.")

    st.divider()

    # Long-term memory
    st.subheader("Long-term memory (Postgres)")
    if token:
        result_lt = get_long_term_memories(token, conversation_id=conv_id)
        if "error" in result_lt:
            st.warning(f"Long-term memory unavailable: {result_lt['error']}")
        else:
            memories = result_lt.get("items", [])
            if not memories:
                st.info("No long-term memories for this conversation.")
            else:
                for mem in memories:
                    preview = str(mem.get("content", ""))[:80]
                    mem_type = mem.get("memory_type", "?")
                    with st.expander(f"[{mem_type}] {preview}"):
                        st.json(mem)
    else:
        st.warning("Not logged in — cannot fetch memory.")


# ---------------------------------------------------------------------------
# Widget admin page
# ---------------------------------------------------------------------------


def _widget_admin_page() -> None:
    st.header("Widget Admin")
    user: dict | None = st.session_state.user

    if user and user.get("role") == "admin":
        st.info(
            "WIDGET-1 not implemented yet. "
            "Widget config API routes are planned for the next phase."
        )
        st.write("When WIDGET-1 is complete, this page will support:")
        st.markdown(
            "- Listing all widget configurations\n"
            "- Creating and editing widgets with allowed origins, themes, and enabled tools\n"
            "- Managing widget access and `is_active` status"
        )
    else:
        st.warning("Admin access required to manage widget configurations.")
        if user:
            st.caption(f"Your role: `{user.get('role', 'unknown')}`")


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="Maintainer's Copilot",
        layout="wide",
    )
    _init_state()

    if not st.session_state.logged_in:
        _login_page()
        return

    user: dict | None = st.session_state.user

    with st.sidebar:
        st.title("Maintainer's Copilot")
        if user:
            st.write(f"**{user.get('email', '')}**")
            st.caption(f"Role: {user.get('role', '')}")
        st.divider()
        page = st.radio(
            "Navigate",
            ["Chat", "Memory Inspector", "Widget Admin"],
            key="nav_page",
        )
        st.divider()
        if st.button("Logout", key="logout_btn"):
            _logout()

    if page == "Chat":
        _chat_page()
    elif page == "Memory Inspector":
        _memory_page()
    elif page == "Widget Admin":
        _widget_admin_page()


if __name__ == "__main__":
    main()
