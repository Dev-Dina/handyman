"""LogisticRegression TF-IDF classifier adapter for model_server."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.paths import ARTIFACTS_DIR

from .schemas import ClassifyResponse

CLASSIFIER_MODEL_NAME = "LogisticRegression TF-IDF"
CLASSIFIER_ARTIFACT_PATH = ARTIFACTS_DIR / "classical" / "best_model.joblib"
_LABELS: frozenset[str] = frozenset({"bug", "feature", "docs", "question"})
_classifier: "IssueClassifier | None" = None


class ClassifierUnavailableError(RuntimeError):
    """Raised when the classifier artifact cannot be loaded or used."""


def _combine_issue_text(title: str, body: str) -> str:
    title = title.strip()
    body = body.strip()
    if body:
        return f"{title}\n\n{body}"
    return title


@dataclass(frozen=True)
class IssueClassifier:
    model: Any
    artifact_path: Path = CLASSIFIER_ARTIFACT_PATH

    @classmethod
    def load(cls, artifact_path: Path = CLASSIFIER_ARTIFACT_PATH) -> "IssueClassifier":
        if not artifact_path.exists():
            raise ClassifierUnavailableError(
                f"classifier artifact not found: {artifact_path}"
            )
        try:
            import joblib  # noqa: PLC0415
        except ImportError as exc:
            raise ClassifierUnavailableError("joblib is not installed") from exc

        try:
            return cls(model=joblib.load(artifact_path), artifact_path=artifact_path)
        except Exception as exc:
            raise ClassifierUnavailableError(
                f"classifier artifact failed to load: {artifact_path}"
            ) from exc

    def classify(self, title: str, body: str = "") -> ClassifyResponse:
        text = _combine_issue_text(title, body)
        try:
            prediction = self.model.predict([text])[0]
        except Exception as exc:
            raise ClassifierUnavailableError("classifier prediction failed") from exc

        label = str(prediction)
        if label not in _LABELS:
            raise ClassifierUnavailableError(
                f"classifier returned invalid label: {label}"
            )

        return ClassifyResponse(
            label=label,  # type: ignore[arg-type]
            confidence=self._confidence(text, label),
            model=CLASSIFIER_MODEL_NAME,
            artifact_path=str(self.artifact_path),
        )

    def _confidence(self, text: str, label: str) -> float | None:
        if not hasattr(self.model, "predict_proba"):
            return None
        try:
            probabilities = self.model.predict_proba([text])[0]
            classes = [str(cls) for cls in getattr(self.model, "classes_", [])]
            if label in classes:
                return float(probabilities[classes.index(label)])
            return float(max(probabilities))
        except Exception:
            return None


def get_classifier() -> IssueClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IssueClassifier.load()
    return _classifier
