"""Finalize the classification golden set: validate curated CSV and write JSONL + summary.

Inputs:
    evals/golden/classification_golden_curated.csv

Outputs:
    evals/golden/classification_golden.jsonl
    evals/golden/classification_golden_summary.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

SOURCE_CSV = Path("evals/golden/classification_golden_curated.csv")
OUTPUT_JSONL = Path("evals/golden/classification_golden.jsonl")
OUTPUT_SUMMARY = Path("evals/golden/classification_golden_summary.json")

EXPECTED_ROWS = 25
VALID_LABELS = {"bug", "feature", "docs", "question"}
EXPECTED_CLASS_COUNTS: dict[str, int] = {
    "bug": 7,
    "feature": 6,
    "docs": 6,
    "question": 6,
}
REQUIRED_FIELDS = (
    "issue_number",
    "title",
    "body_preview",
    "raw_labels",
    "suggested_label",
    "gold_label",
    "curator_notes",
    "created_at",
    "closed_at",
    "html_url",
)


def _load_csv() -> list[dict]:
    with open(SOURCE_CSV, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _validate(rows: list[dict]) -> None:
    errors: list[str] = []

    if len(rows) != EXPECTED_ROWS:
        errors.append(f"row count: expected {EXPECTED_ROWS}, got {len(rows)}")

    missing_fields = [f for f in REQUIRED_FIELDS if f not in (rows[0] if rows else {})]
    if missing_fields:
        errors.append(f"missing columns: {missing_fields}")

    issue_numbers = [r.get("issue_number", "") for r in rows]
    seen: set[str] = set()
    dupes = [n for n in issue_numbers if n in seen or seen.add(n)]  # type: ignore[func-returns-value]
    if dupes:
        errors.append(f"duplicate issue_number: {dupes}")

    empty_ids = [
        i for i, r in enumerate(rows, 1) if not r.get("issue_number", "").strip()
    ]
    if empty_ids:
        errors.append(f"blank issue_number on rows: {empty_ids}")

    invalid_labels = [
        (r.get("issue_number"), r.get("gold_label"))
        for r in rows
        if r.get("gold_label") not in VALID_LABELS
    ]
    if invalid_labels:
        errors.append(f"invalid gold_label: {invalid_labels}")

    empty_notes = [
        r.get("issue_number") for r in rows if not r.get("curator_notes", "").strip()
    ]
    if empty_notes:
        errors.append(f"empty curator_notes on issue_number: {empty_notes}")

    actual_counts: dict[str, int] = {}
    for r in rows:
        lbl = r.get("gold_label", "")
        actual_counts[lbl] = actual_counts.get(lbl, 0) + 1
    for lbl, expected in EXPECTED_CLASS_COUNTS.items():
        actual = actual_counts.get(lbl, 0)
        if actual != expected:
            errors.append(
                f"class count mismatch: {lbl} expected {expected}, got {actual}"
            )

    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)


def _write_jsonl(rows: list[dict]) -> None:
    OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for row in rows:
            record = {field: row.get(field, "") for field in REQUIRED_FIELDS}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_summary(rows: list[dict]) -> None:
    class_counts: dict[str, int] = {}
    for r in rows:
        lbl = r.get("gold_label", "")
        class_counts[lbl] = class_counts.get(lbl, 0) + 1

    summary = {
        "row_count": len(rows),
        "class_counts": class_counts,
        "source_csv": str(SOURCE_CSV),
        "output_jsonl": str(OUTPUT_JSONL),
        "validation_passed": True,
    }
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main() -> None:
    rows = _load_csv()
    _validate(rows)
    _write_jsonl(rows)
    _write_summary(rows)

    summary_counts = {
        lbl: sum(1 for r in rows if r.get("gold_label") == lbl) for lbl in VALID_LABELS
    }
    print(f"OK: {len(rows)} rows validated and written to {OUTPUT_JSONL}")
    print(f"    class counts: {summary_counts}")
    print(f"    summary: {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
