"""Unit tests for model_server LogisticRegression classify endpoint."""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from model_server.classifier import ClassifierUnavailableError
from model_server.main import app
from model_server.schemas import ClassifyResponse

pytestmark = pytest.mark.unit


@dataclass
class _MockClassifier:
    label: str = "bug"
    confidence: float | None = 0.91

    def classify(self, title: str, body: str = "") -> ClassifyResponse:
        assert title == "Pod crash"
        assert isinstance(body, str)
        return ClassifyResponse(
            label=self.label,  # type: ignore[arg-type]
            confidence=self.confidence,
            model="LogisticRegression TF-IDF",
            artifact_path="artifacts/classical/best_model.joblib",
        )


def test_healthz_still_works() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_classify_returns_prediction_when_model_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "model_server.main.get_classifier",
        lambda: _MockClassifier(),
    )
    client = TestClient(app)

    response = client.post(
        "/classify",
        json={"title": "Pod crash", "body": "CrashLoopBackOff"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "label": "bug",
        "confidence": 0.91,
        "model": "LogisticRegression TF-IDF",
        "artifact_path": "artifacts/classical/best_model.joblib",
    }


def test_classify_returns_503_when_artifact_missing(monkeypatch) -> None:
    def _raise_missing() -> None:
        raise ClassifierUnavailableError("classifier artifact not found")

    monkeypatch.setattr("model_server.main.get_classifier", _raise_missing)
    client = TestClient(app)

    response = client.post("/classify", json={"title": "Pod crash", "body": ""})

    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "classifier_unavailable"


def test_model_server_config_does_not_import_app() -> None:
    """model_server/config.py must be self-contained — no app.* imports."""
    import ast

    from app.core.paths import PROJECT_ROOT

    config_src = (PROJECT_ROOT / "model_server" / "config.py").read_text()
    tree = ast.parse(config_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("app"):
                pytest.fail(
                    f"model_server/config.py must not import from app.*: "
                    f"found 'from {node.module} import ...'"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app"):
                    pytest.fail(
                        f"model_server/config.py must not import app.*: "
                        f"found 'import {alias.name}'"
                    )


def test_model_server_classify_does_not_require_torch_import(monkeypatch) -> None:
    sys.modules.pop("torch", None)
    monkeypatch.setattr(
        "model_server.main.get_classifier",
        lambda: _MockClassifier(confidence=None),
    )
    client = TestClient(app)

    response = client.post("/classify", json={"title": "Pod crash", "body": ""})

    assert response.status_code == 200
    assert "torch" not in sys.modules
