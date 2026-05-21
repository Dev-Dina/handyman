"""Runtime constants for model_server."""

from __future__ import annotations

from app.core.paths import ARTIFACTS_DIR

CLASSIFIER_MODEL_NAME = "LogisticRegression TF-IDF"
CLASSIFIER_ARTIFACT_PATH = ARTIFACTS_DIR / "classical" / "best_model.joblib"
CLASSIFIER_ALLOWED_LABELS: frozenset[str] = frozenset(
    {"bug", "feature", "docs", "question"}
)
