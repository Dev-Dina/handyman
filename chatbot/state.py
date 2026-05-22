"""Session state initialization for the AI Ops Control Center."""

from __future__ import annotations

import uuid

import streamlit as st

_DEFAULT_STATE: dict = {
    "logged_in": False,
    "access_token": None,
    "user": None,
    "conversation_id": None,
    "messages": [],
    "tool_calls": [],
    "trace_id": None,
}


def init_state() -> None:
    for key, default in _DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = default


def logout() -> None:
    for key in _DEFAULT_STATE:
        st.session_state[key] = _DEFAULT_STATE[key]
    st.rerun()


def new_conversation() -> None:
    st.session_state.conversation_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.tool_calls = []
    st.session_state.trace_id = None
    st.rerun()
