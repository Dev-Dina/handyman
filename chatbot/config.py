"""Runtime configuration for the Streamlit AI Ops Control Center.

All values are sourced from environment variables with local-dev defaults.
Do not hardcode tokens, secrets, or production URLs here.
"""

from __future__ import annotations

import os

API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
# Browser-facing API origin for generated embed snippets (host pages run in a
# real browser and cannot resolve the internal Docker hostname `api`).
API_PUBLIC_URL: str = os.getenv("API_PUBLIC_URL", "http://localhost:8000")
API_DOCS_URL: str = os.getenv("API_DOCS_URL", "http://localhost:8000/docs")
MODEL_SERVER_URL: str = os.getenv("MODEL_SERVER_URL", "http://localhost:8001")
MODEL_SERVER_PUBLIC_URL: str = os.getenv(
    "MODEL_SERVER_PUBLIC_URL", "http://localhost:8001"
)
STREAMLIT_URL: str = os.getenv("STREAMLIT_URL", "http://localhost:8501")
HOST_DEMO_URL: str = os.getenv("HOST_DEMO_URL", "http://localhost:8080")
# Seeded widget used for the in-app production-widget preview when no admin
# widget list is available. Matches the id baked into demo/host/index.html.
DEFAULT_WIDGET_ID: str = os.getenv(
    "DEFAULT_WIDGET_ID", "99a70ab8-cbff-4615-9b46-f0f0da8064b7"
)
WIDGET_APP_URL: str = os.getenv("WIDGET_APP_URL", "http://localhost:3000/widget-app/")
JAEGER_URL: str = os.getenv("JAEGER_URL", "http://localhost:16686")
MINIO_URL: str = os.getenv("MINIO_URL", "http://localhost:9001")

REQUEST_TIMEOUT: float = 30.0
CHAT_MAX_HISTORY: int = 100
