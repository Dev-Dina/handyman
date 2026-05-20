"""
Count clean single-target Kubernetes issues for classifier labels.

Uses:
    data/raw/kubernetes_issues_augmented.jsonl if present, otherwise
    data/raw/kubernetes_issues.jsonl

Usage:
    .\\.venv\\Scripts\\python.exe ml\\count_clean_single_target.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUGMENTED_INPUT = Path("data/raw/kubernetes_issues_augmented.jsonl")
BASE_INPUT = Path("data/raw/kubernetes_issues.jsonl")
REPORT_JSON = Path("reports/clean_single_target_counts.json")
REPORT_CSV = Path("reports/clean_single_target_counts.csv")
TARGET_LABELS = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}
CLASS_ORDER = ["bug", "feature", "docs", "question"]
DESIRED_CLASS_CAP = 600
EXAMPLES_PER_CLASS = 5


def input_path() -> Path:
    if AUGMENTED_INPUT.exists():
        return AUGMENTED_INPUT
    return BASE_INPUT


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on {path}:{line_number}: {exc}"
                ) from exc
    return records


def target_classes(raw_labels: list[str]) -> set[str]:
    return {
        class_name
        for target_label, class_name in TARGET_LABELS.items()
        if target_label in raw_labels
    }


def example(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "issue_number": record.get("issue_number"),
        "title": record.get("title") or "",
        "html_url": record.get("html_url") or "",
        "raw_labels": record.get("raw_labels") or [],
    }


def build_report(records: list[dict[str, Any]], source_path: Path) -> dict[str, Any]:
    clean_counts: Counter[str] = Counter({class_name: 0 for class_name in CLASS_ORDER})
    examples: dict[str, list[dict[str, Any]]] = {
        class_name: [] for class_name in CLASS_ORDER
    }
    conflict_count = 0
    no_target_count = 0

    for record in records:
        raw_labels = record.get("raw_labels") or []
        if not isinstance(raw_labels, list):
            raw_labels = []

        classes = target_classes([str(label) for label in raw_labels])
        if len(classes) == 1:
            class_name = next(iter(classes))
            clean_counts[class_name] += 1
            if len(examples[class_name]) < EXAMPLES_PER_CLASS:
                examples[class_name].append(example(record))
        elif len(classes) > 1:
            conflict_count += 1
        else:
            no_target_count += 1

    recommended_class_cap = min(clean_counts[class_name] for class_name in CLASS_ORDER)
    possible_600_per_class = recommended_class_cap >= DESIRED_CLASS_CAP
    return {
        "input_path": str(source_path),
        "total_records": len(records),
        "clean_counts": {
            class_name: clean_counts[class_name] for class_name in CLASS_ORDER
        },
        "conflict_count": conflict_count,
        "no_target_count": no_target_count,
        "examples_per_class": examples,
        "possible_600_per_class": possible_600_per_class,
        "recommended_class_cap": recommended_class_cap,
        "target_labels": TARGET_LABELS,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / ".gitkeep").touch(exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_csv_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "class",
                "target_label",
                "clean_count",
                "possible_600_per_class",
            ],
        )
        writer.writeheader()
        label_by_class = {
            class_name: label for label, class_name in TARGET_LABELS.items()
        }
        for class_name in CLASS_ORDER:
            writer.writerow(
                {
                    "class": class_name,
                    "target_label": label_by_class[class_name],
                    "clean_count": report["clean_counts"][class_name],
                    "possible_600_per_class": report["possible_600_per_class"],
                }
            )


def main() -> int:
    source_path = input_path()
    if not source_path.exists():
        print(f"ERROR: {source_path} not found.")
        return 1

    records = read_jsonl(source_path)
    report = build_report(records, source_path)
    write_json_report(report, REPORT_JSON)
    write_csv_report(report, REPORT_CSV)

    print(f"input: {source_path}")
    print(f"clean_counts: {report['clean_counts']}")
    print(f"conflict_count: {report['conflict_count']}")
    print(f"possible_600_per_class: {report['possible_600_per_class']}")
    print(f"recommended_class_cap: {report['recommended_class_cap']}")
    print(f"report_json: {REPORT_JSON}")
    print(f"report_csv: {REPORT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
