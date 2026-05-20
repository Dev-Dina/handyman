"""
Compare classical TF-IDF issue classifiers and save the best model.

Usage:
    uv run python ml/classical/compare_classical.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.text_preprocessing import preprocess_rows  # noqa: E402

TRAIN_PATH = Path("data/processed/train.csv")
VAL_PATH = Path("data/processed/val.csv")
TEST_PATH = Path("data/processed/test.csv")
ARTIFACTS_DIR = Path("artifacts/classical")
REPORTS_DIR = Path("reports/classical")
FIGURES_DIR = Path("reports/figures")

LABELS = ["bug", "feature", "docs", "question"]
VECTORIZER_SETTINGS: dict[str, Any] = {
    "lowercase": True,
    "ngram_range": (1, 2),
    "max_features": 50000,
    "min_df": 2,
    "sublinear_tf": True,
    "strip_accents": "unicode",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def data_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def rows_to_xy(
    rows: list[dict[str, Any]], text_col: str = "model_text"
) -> tuple[list[str], list[str]]:
    def _text(row: dict[str, Any]) -> str:
        if text_col and (v := row.get(text_col)):
            return str(v)
        if v := row.get("model_text"):
            return str(v)
        title = str(row.get("title") or "")
        body = str(row.get("body") or "")
        return f"{title} {body}".strip()

    return (
        [_text(row) for row in rows],
        [str(row.get("final_label") or "") for row in rows],
    )


def validate_labels(rows: list[dict[str, Any]], split_name: str) -> None:
    unknown = sorted({str(row.get("final_label") or "") for row in rows} - set(LABELS))
    if unknown:
        raise ValueError(f"{split_name} contains unsupported labels: {unknown}")


def vectorizer_settings_for_json() -> dict[str, Any]:
    return {**VECTORIZER_SETTINGS, "ngram_range": [1, 2]}


def build_models() -> dict[str, Any]:
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression, SGDClassifier
    from sklearn.naive_bayes import ComplementNB, MultinomialNB
    from sklearn.svm import LinearSVC

    return {
        "DummyClassifier": DummyClassifier(strategy="most_frequent"),
        "ComplementNB": ComplementNB(alpha=0.5),
        "MultinomialNB": MultinomialNB(alpha=0.5),
        "LogisticRegression": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        ),
        "LinearSVC": LinearSVC(
            class_weight="balanced",
            dual="auto",
            random_state=42,
        ),
        "SGDClassifier": SGDClassifier(
            class_weight="balanced",
            loss="modified_huber",
            max_iter=1000,
            random_state=42,
            tol=1e-3,
        ),
    }


def make_pipeline(classifier: Any) -> Any:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline

    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(**VECTORIZER_SETTINGS)),
            ("classifier", classifier),
        ]
    )


def evaluate_model(
    model: Any,
    model_name: str,
    texts: list[str],
    labels: list[str],
) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_recall_fscore_support,
    )

    predict_start = time.perf_counter()
    predictions = model.predict(texts)
    predict_time_seconds = time.perf_counter() - predict_start
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predictions,
        labels=LABELS,
        zero_division=0,
    )
    return {
        "model_name": model_name,
        "accuracy": round(accuracy_score(labels, predictions), 6),
        "macro_f1": round(
            f1_score(labels, predictions, labels=LABELS, average="macro"), 6
        ),
        "weighted_f1": round(
            f1_score(labels, predictions, labels=LABELS, average="weighted"), 6
        ),
        "per_class_precision_recall_f1": {
            label: {
                "precision": round(float(precision[index]), 6),
                "recall": round(float(recall[index]), 6),
                "f1": round(float(f1[index]), 6),
                "support": int(support[index]),
            }
            for index, label in enumerate(LABELS)
        },
        "predict_time_seconds": round(predict_time_seconds, 6),
    }


def write_comparison_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "model_name",
                "accuracy",
                "macro_f1",
                "weighted_f1",
                "fit_time_seconds",
                "predict_time_seconds",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "model_name": row["model_name"],
                    "accuracy": row["accuracy"],
                    "macro_f1": row["macro_f1"],
                    "weighted_f1": row["weighted_f1"],
                    "fit_time_seconds": row["fit_time_seconds"],
                    "predict_time_seconds": row["predict_time_seconds"],
                }
            )


def write_confusion_matrix_csv(path: Path, matrix: list[list[int]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["actual\\predicted", *LABELS])
        for label, row in zip(LABELS, matrix, strict=True):
            writer.writerow([label, *row])


def save_figures(
    comparison_rows: list[dict[str, Any]],
    best_eval: dict[str, Any],
    figures_dir: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures_dir.mkdir(parents=True, exist_ok=True)
    (figures_dir / ".gitkeep").touch(exist_ok=True)

    ordered = sorted(comparison_rows, key=lambda row: row["macro_f1"], reverse=True)
    names = [row["model_name"] for row in ordered]
    scores = [row["macro_f1"] for row in ordered]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(names, scores, color="#4C72B0", alpha=0.85)
    ax.set_ylim(0, max(scores) * 1.15 if scores else 1)
    ax.set_ylabel("Validation macro-F1")
    ax.set_title("Classical Model Comparison")
    ax.tick_params(axis="x", rotation=30)
    for bar, score in zip(bars, scores, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{score:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(figures_dir / "08_classical_model_comparison_macro_f1.png", dpi=150)
    plt.close(fig)

    per_class = best_eval["per_class_precision_recall_f1"]
    class_scores = [per_class[label]["f1"] for label in LABELS]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(LABELS, class_scores, color="#55A868", alpha=0.85)
    ax.set_ylim(0, max(class_scores) * 1.15 if class_scores else 1)
    ax.set_ylabel("Test F1")
    ax.set_title(f"Per-Class F1 ({best_eval['model_name']})")
    for bar, score in zip(bars, class_scores, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{score:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(figures_dir / "09_classical_per_class_f1.png", dpi=150)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare classical issue classifiers.")
    parser.add_argument("--train", type=Path, default=TRAIN_PATH)
    parser.add_argument("--val", type=Path, default=VAL_PATH)
    parser.add_argument("--test", type=Path, default=TEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument(
        "--text-column",
        type=str,
        default="model_text",
        dest="text_column",
        help="Column to use as classifier input text (default: model_text). "
        "Falls back to model_text then title+body if column missing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.train, args.val, args.test):
        if not path.exists():
            print(
                f"ERROR: {path} not found. Run ml/split_dataset.py first.",
                file=sys.stderr,
            )
            return 1

    try:
        import joblib
        from sklearn.metrics import confusion_matrix
    except ImportError as exc:
        print(
            f"ERROR: ML deps missing. Run: uv sync --extra ml\n{exc}", file=sys.stderr
        )
        return 1

    train_rows = preprocess_rows(read_csv(args.train))
    val_rows = preprocess_rows(read_csv(args.val))
    test_rows = preprocess_rows(read_csv(args.test))

    validate_labels(train_rows, "train")
    validate_labels(val_rows, "val")
    validate_labels(test_rows, "test")

    train_texts, train_labels = rows_to_xy(train_rows, args.text_column)
    val_texts, val_labels = rows_to_xy(val_rows, args.text_column)
    test_texts, test_labels = rows_to_xy(test_rows, args.text_column)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)

    comparison_rows: list[dict[str, Any]] = []
    fitted_models: dict[str, Any] = {}
    for model_name, classifier in build_models().items():
        model = make_pipeline(classifier)
        fit_start = time.perf_counter()
        model.fit(train_texts, train_labels)
        fit_time_seconds = time.perf_counter() - fit_start
        metrics = evaluate_model(model, model_name, val_texts, val_labels)
        metrics["fit_time_seconds"] = round(fit_time_seconds, 6)
        comparison_rows.append(metrics)
        fitted_models[model_name] = model

    comparison_rows.sort(key=lambda row: (-row["macro_f1"], row["model_name"]))
    best_name = comparison_rows[0]["model_name"]
    best_model = fitted_models[best_name]
    best_eval = evaluate_model(best_model, best_name, test_texts, test_labels)
    best_eval["fit_time_seconds"] = comparison_rows[0]["fit_time_seconds"]

    test_predictions = best_model.predict(test_texts)
    matrix = confusion_matrix(test_labels, test_predictions, labels=LABELS).tolist()

    generated_at = datetime.now(tz=UTC).isoformat()
    split_counts = {
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "test_count": len(test_rows),
    }
    hash_value = data_hash([args.train, args.val, args.test])
    comparison_report = {
        "generated_at": generated_at,
        "selection_metric": "validation_macro_f1",
        "best_model_name": best_name,
        "labels": LABELS,
        "split_counts": split_counts,
        "vectorizer_settings": vectorizer_settings_for_json(),
        "data_hash": hash_value,
        "validation_results": comparison_rows,
    }
    best_report = {
        "generated_at": generated_at,
        "selection_metric": "validation_macro_f1",
        "selected_from_validation": comparison_rows[0],
        "labels": LABELS,
        "split_counts": split_counts,
        "vectorizer_settings": vectorizer_settings_for_json(),
        "data_hash": hash_value,
        "test_results": best_eval,
    }
    metadata = {
        "generated_at": generated_at,
        "model_name": best_name,
        "model_family": "tfidf_classical",
        "selection_metric": "validation_macro_f1",
        "labels": LABELS,
        "split_counts": split_counts,
        "vectorizer_settings": vectorizer_settings_for_json(),
        "data_hash": hash_value,
    }

    (args.reports_dir / "classical_comparison.json").write_text(
        json.dumps(comparison_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_comparison_csv(args.reports_dir / "classical_comparison.csv", comparison_rows)
    (args.reports_dir / "best_classical_eval.json").write_text(
        json.dumps(best_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_confusion_matrix_csv(args.reports_dir / "confusion_matrix.csv", matrix)
    save_figures(comparison_rows, best_eval, FIGURES_DIR)
    joblib.dump(best_model, args.output_dir / "best_model.joblib")
    (args.output_dir / "best_model_metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"best_model: {best_name}")
    print(f"validation_macro_f1: {comparison_rows[0]['macro_f1']}")
    print(f"test_macro_f1: {best_eval['macro_f1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
