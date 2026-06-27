"""Reusable UI components for the AI Ops Control Center."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

# ── Global design system — the SINGLE CSS-injection layer ────────────────────
# All custom console CSS lives in inject_global_css(). Pages must not inject
# their own styles; they consume the theme + the helper classes defined here.


def inject_global_css(authenticated: bool = True) -> None:
    """Inject the console's global design system. Call once at the top of main().

    `authenticated=False` additionally hides Streamlit's sidebar expand toggle so
    the pre-auth Sign In view shows no sidebar chrome at all (Phase 1 gating leak).
    Defensive rules keep embedded component iframes (the widget preview) visible.
    """
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --brand: #6366F1;           /* indigo-500 — brand accent */
        --brand-strong: #4F46E5;    /* indigo-600 — hover/active */
        --surface: #1E293B;         /* slate-800 — cards / sidebar / inputs */
        --surface-hover: #273449;
        --border: rgba(148, 163, 184, 0.18);
        --text: #E2E8F0;            /* slate-200 */
        --muted: #94A3B8;           /* slate-400 */
        --radius: 12px;
    }

    /* Typography — Inter across the app, with a system fallback chain */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    button, input, textarea, select {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* Spacing rhythm — roomier, capped main column */
    [data-testid="stMainBlockContainer"], .block-container {
        padding-top: 2.4rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    /* Sidebar surface */
    [data-testid="stSidebar"] {
        background: var(--surface);
        border-right: 1px solid var(--border);
    }

    /* Metric → card */
    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 0.9rem 1.1rem;
    }
    [data-testid="stMetricLabel"] p { color: var(--muted); font-weight: 500; }

    /* Expander → card */
    [data-testid="stExpander"] {
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        background: var(--surface);
        overflow: hidden;
    }

    /* Buttons — shared shape + motion */
    .stButton > button,
    [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
        border-radius: 10px;
        font-weight: 600;
        transition: transform .05s ease, box-shadow .18s ease,
                    background .18s ease, border-color .18s ease;
    }
    .stButton > button:hover { transform: translateY(-1px); }
    .stButton > button:active { transform: translateY(0); }
    /* Primary */
    .stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
        background: var(--brand); border: 1px solid var(--brand); color: #fff;
    }
    .stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
        background: var(--brand-strong); border-color: var(--brand-strong);
        box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35);
    }
    /* Secondary */
    .stButton > button[kind="secondary"], [data-testid="stBaseButton-secondary"] {
        background: transparent; border: 1px solid var(--border); color: var(--text);
    }
    .stButton > button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover {
        border-color: var(--brand); color: #fff; background: var(--surface-hover);
    }

    /* Inputs */
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
    [data-baseweb="input"], [data-baseweb="select"] > div {
        border-radius: 10px !important;
    }
    [data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus {
        border-color: var(--brand) !important;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25) !important;
    }

    /* Defensive — never hide/clip embedded component iframes (widget preview) */
    [data-testid="stIFrame"], [data-testid="stIFrame"] iframe { display: block; }
    iframe { border: none; }

    /* Reusable helper classes — available for pages, not yet applied */
    .console-section-header {
        margin: 0.2rem 0 1rem 0; padding-left: 0.75rem;
        border-left: 3px solid var(--brand);
    }
    .console-section-title {
        font-size: 1.15rem; font-weight: 700; color: var(--text); letter-spacing: -0.01em;
    }
    .console-section-sub { font-size: 0.85rem; color: var(--muted); margin-top: 0.15rem; }
    .console-card {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1rem 1.2rem;
    }
    .console-card-label {
        font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted);
    }
    .console-card-value {
        font-size: 1.6rem; font-weight: 700; color: var(--text); margin-top: 0.15rem;
    }
    .console-card-caption { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }

    /* ── Login split landing — scoped to the row containing .login-left ── */
    [data-testid="stHorizontalBlock"]:has(.login-left) { align-items: stretch; }
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stColumn"] {
        display: flex; flex-direction: column; justify-content: center;
    }
    /* login form: strip default chrome, dark inputs, full-height submit */
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stForm"] {
        border: none; padding: 0; background: transparent; box-shadow: none;
    }
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stTextInput"] [data-baseweb="base-input"],
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stTextInput"] input {
        background-color: #1E293B !important;
        color: #F1F5F9 !important;
    }
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stTextInput"] [data-baseweb="base-input"] {
        border: 1px solid #334155 !important;
        border-radius: 10px !important;
        min-height: 42px !important;
    }
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stTextInput"] input::placeholder {
        color: #64748B !important;
    }
    [data-testid="stHorizontalBlock"]:has(.login-left) [data-testid="stFormSubmitButton"] button {
        height: 44px;
    }

    /* Left marketing panel */
    .login-left {
        min-height: 520px;
        display: flex; flex-direction: column; justify-content: center;
        padding: 2.5rem 2rem 2.5rem 0.25rem;
    }
    .login-logo { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.6rem; }
    .login-logo-mark {
        width: 34px; height: 34px; border-radius: 9px; background: var(--brand);
        color: #fff; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto;
    }
    .login-logo-mark svg { width: 19px; height: 19px; }
    .login-logo-text { font-size: 1rem; font-weight: 600; color: #F1F5F9; }
    .login-pill {
        display: inline-flex; align-items: center; gap: 0.45rem; width: fit-content;
        background: var(--surface); border: 1px solid var(--border);
        color: #CBD5E1; font-size: 0.78rem; font-weight: 500;
        padding: 0.3rem 0.7rem; border-radius: 999px; margin-bottom: 1.5rem;
    }
    .login-pill-dot {
        width: 7px; height: 7px; border-radius: 50%; background: #22C55E;
        box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
    }
    .login-headline {
        font-size: 30px; font-weight: 500; line-height: 1.2; color: #F1F5F9;
        letter-spacing: -0.02em; margin-bottom: 1rem; max-width: 20ch;
    }
    .login-sub {
        font-size: 0.95rem; color: var(--muted); line-height: 1.55;
        max-width: 46ch; margin-bottom: 2rem;
    }
    .login-caps { display: flex; flex-direction: column; gap: 0.9rem; }
    .login-cap {
        display: flex; align-items: center; gap: 0.7rem;
        color: #E2E8F0; font-size: 0.92rem; font-weight: 500;
    }
    .login-cap-icon {
        width: 30px; height: 30px; border-radius: 8px; flex: 0 0 auto;
        background: rgba(99, 102, 241, 0.12); color: #818CF8;
        display: inline-flex; align-items: center; justify-content: center;
    }
    .login-cap-icon svg { width: 16px; height: 16px; }

    /* Right sign-in panel */
    .login-signin-title { font-size: 21px; font-weight: 500; color: #F1F5F9; }
    .login-signin-sub { font-size: 0.88rem; color: var(--muted); margin: 0.25rem 0 1.2rem 0; }
    .login-signup-hint { font-size: 0.85rem; color: var(--muted); margin-top: 1rem; }
    .login-signup-link { color: #818CF8; font-weight: 500; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    if not authenticated:
        st.markdown(
            "<style>"
            '[data-testid="stSidebarCollapsedControl"],'
            '[data-testid="collapsedControl"]{display:none !important;}'
            "</style>",
            unsafe_allow_html=True,
        )


def section_header(title: str, subtitle: str | None = None) -> None:
    """Styled section header (accent bar + title). Available; not yet applied to pages."""
    sub = f'<div class="console-section-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="console-section-header">'
        f'<div class="console-section-title">{title}</div>{sub}</div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, caption: str | None = None) -> None:
    """Styled metric card. Available; not yet applied to pages."""
    cap = f'<div class="console-card-caption">{caption}</div>' if caption else ""
    st.markdown(
        f'<div class="console-card">'
        f'<div class="console-card-label">{label}</div>'
        f'<div class="console-card-value">{value}</div>{cap}</div>',
        unsafe_allow_html=True,
    )


def status_badge(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚠️"


_LIFECYCLE_BADGES = {
    "deployed": "🟢 Deployed",
    "offline": "🟠 Offline",
    "experimental": "🔵 Experimental",
    "gap": "🔴 Gap",
}


def lifecycle_badge(status: str) -> str:
    """Map a lifecycle word to a coloured badge: deployed/offline/experimental/gap."""
    return _LIFECYCLE_BADGES.get(status.lower(), status)


def page_proves(text: str) -> None:
    """Render a one-line 'what this page proves' note under a page title."""
    st.caption(f"🎯 **What this page proves:** {text}")


def widget_preview_url(widget_id: str | None, host_demo_url: str) -> str:
    """Build the host-demo URL that loads the production widget for a given id."""
    base = host_demo_url.rstrip("/")
    return f"{base}/?widget_id={widget_id}" if widget_id else f"{base}/"


def render_widget_preview(
    widget_id: str | None, host_demo_url: str, height: int = 720
) -> None:
    """Embed the external host demo (which loads /widget.js → the React widget).

    Uses the real production flow: this iframe frames the host page, which injects
    the widget loader and renders the bottom-right bubble. Falls back to a link if
    the iframe is blocked by the browser.
    """
    url = widget_preview_url(widget_id, host_demo_url)
    st.components.v1.iframe(url, height=height, scrolling=True)
    st.caption(
        f"Live production React widget embedded via the host demo. "
        f"[Open full host demo]({url})"
    )


def parse_json_if_possible(value: Any) -> Any:
    """Return a parsed object if value looks like JSON, else the original value."""
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s[:1] in ("{", "["):
            try:
                return json.loads(s)
            except (json.JSONDecodeError, ValueError):
                return value
    return value


def clean_preview_text(text: Any, max_chars: int = 300) -> str:
    """Collapse escaped/real newlines and whitespace into a readable one-line preview."""
    if not isinstance(text, str):
        text = str(text)
    cleaned = text.replace("\\n", " ").replace("\\t", " ").replace("\\r", " ")
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + "…"
    return cleaned


def render_rag_chunks(results: list[dict]) -> None:
    """Render retrieved RAG chunks as compact, readable cards.

    Works for both the RAG Explorer payload (chunk_id + score present) and the
    chat rag_query tool payload (text + source_type only).
    """
    if not results:
        st.caption("No chunks returned.")
        return
    for i, chunk in enumerate(results, 1):
        source = chunk.get("source_type", "?")
        score = chunk.get("score")
        score_str = f"{score:.4f}" if isinstance(score, (int, float)) else "—"
        text = chunk.get("text", "")
        preview = clean_preview_text(text, 80)
        with st.expander(f"#{i} · [{source}] · score={score_str} — {preview}"):
            chunk_id = chunk.get("chunk_id")
            if chunk_id:
                st.caption(f"chunk_id: `{chunk_id}`")
            # st.text preserves raw newlines/markdown literally — no badge/heading
            # rendering surprises from noisy Kubernetes doc/issue chunks.
            st.text(text)


def render_tool_call(record: dict) -> None:
    """Render a single chat tool-call record as a structured card.

    Falls back to a raw-JSON expander so nothing is hidden.
    """
    name = record.get("tool_name") or record.get("tool") or "tool"
    error = record.get("error")

    if error:
        st.markdown(f"**🔧 `{name}`** — ❌ error")
        st.caption(clean_preview_text(error, 300))
        with st.expander("Show raw JSON"):
            st.json(record)
        return

    parsed = parse_json_if_possible(record.get("result"))
    st.markdown(f"**🔧 `{name}`** — ✅")

    if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
        # RAG-style payload: {"retriever": ..., "results": [...]}
        st.caption(
            f"retriever: `{parsed.get('retriever', '—')}` · "
            f"results: {len(parsed['results'])}"
        )
        render_rag_chunks(parsed["results"])
    elif isinstance(parsed, dict):
        # classify / entities / summarize style: show fields cleanly
        for key, val in parsed.items():
            st.caption(f"**{key}**: {clean_preview_text(val, 200)}")
    elif parsed is not None:
        st.caption(clean_preview_text(parsed, 400))

    with st.expander("Show raw JSON"):
        st.json(record)
