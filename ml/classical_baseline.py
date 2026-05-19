"""
Train and evaluate a classical TF-IDF + LogisticRegression issue classifier.

Usage:
    uv run python ml/classical_baseline.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
import sys
import time
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from text_preprocessing import preprocess_rows

TRAIN_PATH = Path("data/processed/train.csv")
VAL_PATH = Path("data/processed/val.csv")
TEST_PATH = Path("data/processed/test.csv")
ARTIFACTS_DIR = Path("artifacts/classical")
REPORTS_DIR = Path("reports")
FIGURES_DIRNAME = "figures"

LABELS = ["bug", "feature", "docs", "question"]
MODEL_NAME = "tfidf_logistic_regression"


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


def rows_to_xy(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    texts = [str(row.get("model_text") or "") for row in rows]
    labels = [str(row.get("final_label") or "") for row in rows]
    return texts, labels


def validate_labels(rows: list[dict[str, Any]], split_name: str) -> None:
    unknown = sorted({str(row.get("final_label") or "") for row in rows} - set(LABELS))
    if unknown:
        raise ValueError(f"{split_name} contains unsupported labels: {unknown}")


def per_class_report(
    precision: list[float],
    recall: list[float],
    f1: list[float],
    support: list[int],
) -> dict[str, dict[str, float | int]]:
    return {
        label: {
            "precision": round(precision[index], 6),
            "recall": round(recall[index], 6),
            "f1": round(f1[index], 6),
            "support": int(support[index]),
        }
        for index, label in enumerate(LABELS)
    }


def write_confusion_matrix_csv(path: Path, matrix: list[list[int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["actual\\predicted", *LABELS])
        for label, row in zip(LABELS, matrix, strict=True):
            writer.writerow([label, *row])


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def write_fallback_png(path: Path, matrix: list[list[int]]) -> None:
    cell = 80
    size = cell * len(LABELS)
    max_value = max(max(row) for row in matrix) or 1
    rows: list[bytes] = []
    for y in range(size):
        matrix_row = y // cell
        scanline = bytearray()
        for x in range(size):
            matrix_col = x // cell
            value = matrix[matrix_row][matrix_col] / max_value
            intensity = 255 - int(210 * math.sqrt(value))
            border = x % cell in {0, cell - 1} or y % cell in {0, cell - 1}
            if border:
                scanline.extend((40, 40, 40))
            else:
                scanline.extend((intensity, intensity, 255))
        rows.append(b"\x00" + bytes(scanline))

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def write_confusion_matrix_png(path: Path, matrix: list[list[int]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        write_fallback_png(path, matrix)
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(len(LABELS)), LABELS, rotation=35, ha="right")
    axis.set_yticks(range(len(LABELS)), LABELS)
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Actual")
    axis.set_title("Classical Baseline Confusion Matrix")
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            axis.text(col_index, row_index, str(value), ha="center", va="center")
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train TF-IDF + LogisticRegression issue classifier."
    )
    parser.add_argument("--train", type=Path, default=TRAIN_PATH)
    parser.add_argument("--val", type=Path, default=VAL_PATH)
    parser.add_argument("--test", type=Path, default=TEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
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
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            f1_score,
            precision_recall_fscore_support,
        )
        from sklearn.pipeline import Pipeline
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

    train_texts, train_labels = rows_to_xy(train_rows)
    test_texts, test_labels = rows_to_xy(test_rows)

    vectorizer_settings: dict[str, Any] = {
        "lowercase": True,
        "ngram_range": (1, 2),
        "max_features": 50000,
        "min_df": 2,
        "sublinear_tf": True,
        "strip_accents": "unicode",
    }
    model = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(**vectorizer_settings)),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    n_jobs=None,
                    random_state=42,
                ),
            ),
        ]
    )

    fit_start = time.perf_counter()
    model.fit(train_texts, train_labels)
    fit_time_seconds = time.perf_counter() - fit_start

    predict_start = time.perf_counter()
    predictions = model.predict(test_texts)
    predict_time_seconds = time.perf_counter() - predict_start

    precision, recall, f1, support = precision_recall_fscore_support(
        test_labels,
        predictions,
        labels=LABELS,
        zero_division=0,
    )
    matrix = confusion_matrix(test_labels, predictions, labels=LABELS).tolist()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.reports_dir / FIGURES_DIRNAME
    figures_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, args.output_dir / "model.joblib")
    write_confusion_matrix_csv(
        args.reports_dir / "classical_confusion_matrix.csv", matrix
    )
    write_confusion_matrix_png(
        figures_dir / "07_classical_confusion_matrix.png",
        matrix,
    )

    report = {
        "train_count": len(train_rows),
        "val_count": len(val_rows),
        "test_count": len(test_rows),
        "accuracy": round(accuracy_score(test_labels, predictions), 6),
        "macro_f1": round(
            f1_score(test_labels, predictions, labels=LABELS, average="macro"), 6
        ),
        "weighted_f1": round(
            f1_score(test_labels, predictions, labels=LABELS, average="weighted"), 6
        ),
        "per_class_precision_recall_f1": per_class_report(
            precision.tolist(),
            recall.tolist(),
            f1.tolist(),
            support.tolist(),
        ),
        "fit_time_seconds": round(fit_time_seconds, 6),
        "predict_time_seconds": round(predict_time_seconds, 6),
        "model_name": MODEL_NAME,
        "vectorizer_settings": {**vectorizer_settings, "ngram_range": [1, 2]},
        "data_hash": data_hash([args.train, args.val, args.test]),
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    (args.reports_dir / "classical_eval.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"model: {args.output_dir / 'model.joblib'}")
    print(f"report: {args.reports_dir / 'classical_eval.json'}")
    print(f"accuracy: {report['accuracy']}")
    print(f"macro_f1: {report['macro_f1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
