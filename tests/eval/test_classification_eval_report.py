"""Eval tests for classification golden set and CI-safe eval report."""

from __future__ import annotations

import importlib.util
import json

import pytest

from app.core.paths import EVALS_DIR, REPORTS_DIR
from ml.classifier_config import LABELS

pytestmark = pytest.mark.eval

_GOLDEN_JSONL = EVALS_DIR / "golden" / "classification_golden.jsonl"
_REPORT_PATH = REPORTS_DIR / "classification_eval_report.json"
_EXPECTED_ROWS = 25
_REPORT_REQUIRED_KEYS = {
    "generated_at",
    "model",
    "artifact_path",
    "golden_path",
    "row_count",
    "accuracy",
    "macro_f1",
    "per_class_f1",
    "thresholds",
    "threshold_passed",
}


def _load_jsonl() -> list[dict]:
    with _GOLDEN_JSONL.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_no_torch_in_main_ci_environment() -> None:
    assert importlib.util.find_spec("torch") is None


def test_classification_golden_jsonl_has_expected_rows() -> None:
    rows = _load_jsonl()
    assert len(rows) == _EXPECTED_ROWS


def test_classification_golden_jsonl_labels_valid() -> None:
    rows = _load_jsonl()
    labels = {row.get("gold_label") for row in rows}
    assert labels <= set(LABELS)
    assert labels == set(LABELS)


def test_classification_eval_report_schema_if_present() -> None:
    if not _REPORT_PATH.exists():
        pytest.skip("classification_eval_report.json not generated")
    report = json.loads(_REPORT_PATH.read_text(encoding="utf-8"))
    missing = _REPORT_REQUIRED_KEYS - set(report)
    assert not missing, f"Report missing keys: {missing}"
    assert report["row_count"] == _EXPECTED_ROWS
    assert 0.0 <= report["accuracy"] <= 1.0
    assert 0.0 <= report["macro_f1"] <= 1.0
    assert set(report["per_class_f1"]) == set(LABELS)
    assert isinstance(report["threshold_passed"], bool)


def test_classification_eval_report_meets_threshold_if_present() -> None:
    if not _REPORT_PATH.exists():
        pytest.skip("classification_eval_report.json not generated")
    report = json.loads(_REPORT_PATH.read_text(encoding="utf-8"))
    assert report["threshold_passed"], (
        f"classification macro_f1 {report['macro_f1']} below "
        f"threshold {report['thresholds']['macro_f1_min']}"
    )
