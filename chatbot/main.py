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
from chatbot.components import inject_global_css
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


# Inline-SVG icons (stroke=currentColor → coloured by the CSS layer). If a future
# sanitizer strips SVG, the adjacent text labels still render — nothing breaks.
_ICON_WRENCH = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 '
    '1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 '
    '0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'
)
_ICON_TAG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 '
    '7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
    '<line x1="7" y1="7" x2="7.01" y2="7"/></svg>'
)
_ICON_DATABASE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" '
    'ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 '
    '3 9 3s9-1.34 9-3V5"/></svg>'
)
_ICON_CHAT = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 '
    '1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 '
    '1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>'
    "</svg>"
)

_LOGIN_LEFT_HTML = f"""
<div class="login-left">
  <div class="login-logo">
    <span class="login-logo-mark">{_ICON_WRENCH}</span>
    <span class="login-logo-text">Maintainer's Copilot</span>
  </div>
  <div class="login-pill"><span class="login-pill-dot"></span>AI ops console</div>
  <div class="login-headline">Triage, route, and answer maintainer issues — fast.</div>
  <div class="login-sub">A copilot that classifies incoming issues, retrieves the
  right docs, and drafts grounded replies with full trace visibility.</div>
  <div class="login-caps">
    <div class="login-cap"><span class="login-cap-icon">{_ICON_TAG}</span>
      <span>Multi-label issue classification</span></div>
    <div class="login-cap"><span class="login-cap-icon">{_ICON_DATABASE}</span>
      <span>Hybrid RAG over your corpus</span></div>
    <div class="login-cap"><span class="login-cap-icon">{_ICON_CHAT}</span>
      <span>Tool-calling chat with trace IDs</span></div>
  </div>
</div>
"""

_LOGIN_SIGNIN_HEAD_HTML = (
    '<div class="login-signin-title">Sign in</div>'
    '<div class="login-signin-sub">Welcome back. Enter your details.</div>'
)

_LOGIN_SIGNUP_HINT_HTML = (
    '<div class="login-signup-hint">No account? '
    '<span class="login-signup-link">Create one</span></div>'
)


def _login_page() -> None:
    """Split landing: marketing on the left, the real sign-in form on the right.

    Logged-out view only (no sidebar/nav — Phase 1 gating). Presentation only;
    the email/password form still calls login() → /api/v1/auth/login unchanged.
    """
    left, right = st.columns([1.15, 1], gap="large")

    with left:
        st.markdown(_LOGIN_LEFT_HTML, unsafe_allow_html=True)

    with right:
        st.markdown(_LOGIN_SIGNIN_HEAD_HTML, unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input(
                "Password", type="password", placeholder="••••••••"
            )
            submitted = st.form_submit_button(
                "Sign in", type="primary", use_container_width=True
            )
        st.markdown(_LOGIN_SIGNUP_HINT_HTML, unsafe_allow_html=True)

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
    inject_global_css(authenticated=st.session_state.logged_in)

    # Auth gate: a logged-out visitor gets only the centered Sign In view. No
    # sidebar, nav, or user chrome is rendered until this check passes.
    if not st.session_state.logged_in:
        _login_page()
        return

    _render_authenticated_app()


if __name__ == "__main__":
    main()
