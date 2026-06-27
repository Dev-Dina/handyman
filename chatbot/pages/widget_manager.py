"""Widget Manager page — configure the production embeddable React widget."""

from __future__ import annotations

import streamlit as st

import chatbot.api_client as client
from chatbot.components import lifecycle_badge, page_proves, render_widget_preview
from chatbot.config import API_PUBLIC_URL, HOST_DEMO_URL, WIDGET_APP_URL
from chatbot.pages._shared import ALL_TOOLS, EMBED_SNIPPET_TEMPLATE


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
                    snippet = EMBED_SNIPPET_TEMPLATE.format(
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
            options=ALL_TOOLS,
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

    snippet = EMBED_SNIPPET_TEMPLATE.format(
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
