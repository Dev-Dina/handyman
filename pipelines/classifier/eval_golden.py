"""CI-safe classification golden-set eval for the classical fallback model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import EVALS_DIR, RAW_DATA_DIR, REPORTS_DIR
from ml.classifier_config import LABELS
from model_server.config import CLASSIFIER_ARTIFACT_PATH, CLASSIFIER_MODEL_NAME

GOLDEN_PATH = EVALS_DIR / "golden" / "classification_golden.jsonl"
RAW_ISSUES_PATH = RAW_DATA_DIR / "kubernetes_issues.jsonl"
REPORT_PATH = REPORTS_DIR / "classification_eval_report.json"
THRESHOLDS_PATH = Path("eval_thresholds.yaml")
_DEFAULT_MACRO_F1_MIN = 0.65


def _load_threshold() -> float:
    if not THRESHOLDS_PATH.exists():
        return _DEFAULT_MACRO_F1_MIN
    try:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(THRESHOLDS_PATH.read_text(encoding="utf-8")) or {}
        return float(data["classification"]["macro_f1_min"])
    except Exception:
        text = THRESHOLDS_PATH.read_text(encoding="utf-8")
        in_classification = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line:
                continue
            if line.startswith("classification:"):
                in_classification = True
                continue
            if line and not line.startswith((" ", "\t")):
                in_classification = False
            if in_classification and "macro_f1_min:" in line:
                return float(line.split(":", 1)[1].strip())
        return _DEFAULT_MACRO_F1_MIN


def _load_golden(path: Path = GOLDEN_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _load_raw_issue_text(path: Path = RAW_ISSUES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    issue_text: dict[str, str] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            issue_number = str(row.get("issue_number", "")).strip()
            if issue_number:
                issue_text[issue_number] = _row_text(row)
    return issue_text


def _row_text(row: dict[str, Any]) -> str:
    title = str(row.get("title") or "").strip()
    body = str(
        row.get("body") or row.get("body_preview") or row.get("text") or ""
    ).strip()
    return f"{title}\n\n{body}" if body else title


def _gold_label(row: dict[str, Any]) -> str:
    label = str(row.get("gold_label") or row.get("label") or "").strip()
    if label not in LABELS:
        raise ValueError(f"invalid gold label: {label!r}")
    return label


def _pure_metrics(preds: list[str], refs: list[str]) -> dict[str, Any]:
    n = len(refs)
    accuracy = sum(p == r for p, r in zip(preds, refs, strict=True)) / n if n else 0.0
    per_class: dict[str, dict[str, float]] = {}
    for label in LABELS:
        tp = sum(
            1 for p, r in zip(preds, refs, strict=True) if p == label and r == label
        )
        fp = sum(
            1 for p, r in zip(preds, refs, strict=True) if p == label and r != label
        )
        fn = sum(
            1 for p, r in zip(preds, refs, strict=True) if p != label and r == label
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(per_class)
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class_f1": {label: data["f1"] for label, data in per_class.items()},
        "per_class": per_class,
    }


def main() -> None:
    if not GOLDEN_PATH.exists():
        raise FileNotFoundError(f"golden set not found: {GOLDEN_PATH}")
    if not CLASSIFIER_ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"classifier artifact not found: {CLASSIFIER_ARTIFACT_PATH}"
        )

    import joblib  # noqa: PLC0415

    rows = _load_golden()
    raw_issue_text = _load_raw_issue_text()
    texts = [
        raw_issue_text.get(str(row.get("issue_number", "")).strip(), _row_text(row))
        for row in rows
    ]
    refs = [_gold_label(row) for row in rows]
    model = joblib.load(CLASSIFIER_ARTIFACT_PATH)
    preds = [str(pred) for pred in model.predict(texts)]
    invalid = sorted(set(preds) - set(LABELS))
    if invalid:
        raise ValueError(f"classifier returned invalid labels: {invalid}")

    threshold = _load_threshold()
    metrics = _pure_metrics(preds, refs)
    threshold_passed = metrics["macro_f1"] >= threshold
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": CLASSIFIER_MODEL_NAME,
        "artifact_path": str(CLASSIFIER_ARTIFACT_PATH),
        "golden_path": str(GOLDEN_PATH),
        "raw_issues_path": str(RAW_ISSUES_PATH),
        "input_text_source": "raw_issue_title_body_with_golden_fallback",
        "row_count": len(rows),
        "thresholds": {"macro_f1_min": threshold},
        "threshold_passed": threshold_passed,
        **metrics,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"accuracy={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f} "
        f"threshold={threshold:.4f} passed={threshold_passed}"
    )
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
