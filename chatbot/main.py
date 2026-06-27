"""Maintainer's Copilot — AI Ops Control Center (Streamlit).

Unified dashboard for the Handyman project: classifier, RAG, chat,
memory, widget management, observability, and MinIO artifacts in one app.

Calls the FastAPI backend over HTTP. JWT stored in st.session_state only.
No direct DB, Redis, or Vault access. No business logic duplicated here.
"""

from __future__ import annotations

import uuid

import streamlit as st

from chatbot.api_client import login
from chatbot.pages import (
    page_artifacts,
    page_chat,
    page_classifier,
    page_demo_runbook,
    page_eval_defense,
    page_memory,
    page_observability,
    page_overview,
    page_rag_explorer,
    page_system_health,
    page_widget_manager,
)
from chatbot.state import init_state, logout

_PAGES = [
    "Overview",
    "System Health",
    "Evaluation Defense",
    "Classifier Playground",
    "RAG Explorer",
    "Chat Copilot",
    "Memory Inspector",
    "Widget Manager",
    "Observability",
    "Artifacts / MinIO",
    "Demo Runbook",
]

_PAGE_FN = {
    "Overview": page_overview,
    "System Health": page_system_health,
    "Evaluation Defense": page_eval_defense,
    "Classifier Playground": page_classifier,
    "RAG Explorer": page_rag_explorer,
    "Chat Copilot": page_chat,
    "Memory Inspector": page_memory,
    "Widget Manager": page_widget_manager,
    "Observability": page_observability,
    "Artifacts / MinIO": page_artifacts,
    "Demo Runbook": page_demo_runbook,
}


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


def _render_authenticated_app() -> None:
    """Render the sidebar nav and dispatch the selected page.

    Only reached after the auth gate in main() passes, so the sidebar chrome
    and the _PAGES/_PAGE_FN navigation are never constructed for a logged-out
    visitor.
    """
    user: dict | None = st.session_state.user

    with st.sidebar:
        st.title("Maintainer's Copilot")
        st.caption("AI Ops Control Center")
        if user:
            st.write(f"**{user.get('email', '')}**")
            st.caption(f"Role: {user.get('role', '')}")
        st.divider()
        page = st.radio("Navigate", _PAGES, key="nav_page")
        st.divider()
        if st.button("Logout", key="logout_btn"):
            logout()

    _PAGE_FN[page]()


def main() -> None:
    init_state()
    st.set_page_config(
        page_title="Maintainer's Copilot — AI Ops",
        layout="wide",
        initial_sidebar_state="expanded" if st.session_state.logged_in else "collapsed",
    )

    # Auth gate: a logged-out visitor gets only the centered Sign In view. No
    # sidebar, nav, or user chrome is rendered until this check passes.
    if not st.session_state.logged_in:
        _login_page()
        return

    _render_authenticated_app()


if __name__ == "__main__":
    main()
