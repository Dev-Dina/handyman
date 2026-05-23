"""Runtime constants for model_server.

Intentionally self-contained — no app.* imports so model_server runs in its
own Docker image without the main app package installed.
"""

from __future__ import annotations

import os
from pathlib import Path

CLASSIFIER_MODEL_NAME = "LogisticRegression TF-IDF"

# Env var override → file-relative fallback (parent is model_server/, grandparent is
# project root locally and /app in Docker, so the same expression resolves correctly
# in both environments).
_env_path = os.getenv("CLASSIFIER_ARTIFACT_PATH")
CLASSIFIER_ARTIFACT_PATH: Path = (
    Path(_env_path)
    if _env_path
    else Path(__file__).parent.parent / "artifacts" / "classical" / "best_model.joblib"
)

CLASSIFIER_ALLOWED_LABELS: frozenset[str] = frozenset(
    {"bug", "feature", "docs", "question"}
)

# ── Embedding model (E5) for RAG dense/hybrid retrieval ──────────────────────
# Default points at a model dir shipped into the image (offline-cached weights),
# falling back to the HuggingFace hub id if the local dir is absent.
EMBED_MODEL_NAME: str = os.getenv("EMBED_MODEL_NAME", "intfloat/e5-small-v2")
_embed_local = os.getenv("EMBED_MODEL_PATH")
EMBED_MODEL_PATH: str = (
    _embed_local
    if _embed_local
    else str(Path(__file__).parent.parent / "artifacts" / "embeddings" / "e5-small-v2")
)
EMBED_DIMENSION: int = 384
EMBED_MAX_LENGTH: int = 512
