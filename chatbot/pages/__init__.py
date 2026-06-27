"""Page implementations for the AI Ops Control Center.

Each module renders one section of the Streamlit dashboard; ``chatbot.main``
maps the sidebar navigation labels to these functions. Re-exported here so the
public import surface (``from chatbot.pages import page_*``) is unchanged.
"""

from chatbot.pages.artifacts import page_artifacts
from chatbot.pages.chat import page_chat
from chatbot.pages.classifier import page_classifier
from chatbot.pages.demo_runbook import page_demo_runbook
from chatbot.pages.eval_defense import page_eval_defense
from chatbot.pages.memory import page_memory
from chatbot.pages.observability import page_observability
from chatbot.pages.overview import page_overview
from chatbot.pages.rag_explorer import page_rag_explorer
from chatbot.pages.system_health import page_system_health
from chatbot.pages.widget_manager import page_widget_manager

__all__ = [
    "page_overview",
    "page_system_health",
    "page_chat",
    "page_rag_explorer",
    "page_classifier",
    "page_memory",
    "page_widget_manager",
    "page_observability",
    "page_artifacts",
    "page_eval_defense",
    "page_demo_runbook",
]
