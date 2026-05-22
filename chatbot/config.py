"""Runtime configuration for the Streamlit chatbot client.

All values are sourced from environment variables with local-dev defaults.
Do not hardcode tokens, secrets, or production URLs here.
"""

from __future__ import annotations

import os

API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")

REQUEST_TIMEOUT: float = 30.0
CHAT_MAX_HISTORY: int = 100
