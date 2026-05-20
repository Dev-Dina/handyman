"""
Audit and materialize cleaned classifier splits without overwriting originals.

Usage:
    .\\.venv\\Scripts\\python.exe ml\\clean_processed_splits.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from text_preprocessing import build_model_text, text_quality_flags

INPUT_DIR = Path("data/processed")
OUTPUT_DIR = Path("data/processed_cleaned")
REPORT_PATH = Path("reports/cleaning_audit_report.json")
EXAMPLES_PATH = Path("reports/cleaning_examples.csv")
SPLITS = ("train", "val", "test")
QUALITY_COLUMNS = (
    "has_non_ascii",
    "non_ascii_ratio",
    "mostly_non_ascii_candidate",
    "empty_body",
    "very_long",
)
EXAMPLE_LIMIT = 25
EXAMPLE_TEXT_LIMIT = 500

_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]*\)")
_DETAILS_RE = re.compile(r"</?details>", re.IGNORECASE)
_NO_RESPONSE_RE = re.compile(r"(?im)^\s*_?No response_?\s*$")
_EMPTY_HEADING_RE = re.compile(r"(?ms)^### [^\n]+\n(?=\s*(?:^### |\Z))")
_EXCESS_BLANK_RE = re.compile(r"\n{3,}")
_HORIZONTAL_SPACE_RE = re.compile(r"[ \t]+")
_MOJIBAKE_REPLACEMENTS = {
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "â€�": '"',
    "â€“": "-",
    "â€”": "-",
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def fix_mojibake(text: str) -> str:
    for bad, good in _MOJIBAKE_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text


def clean_body(body: str) -> str:
    cleaned = fix_mojibake(body or "")
    cleaned = _IMAGE_RE.sub("<IMAGE>", cleaned)
    cleaned = _DETAILS_RE.sub("", cleaned)
    cleaned = _NO_RESPONSE_RE.sub("", cleaned)
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _EMPTY_HEADING_RE.sub("", cleaned)
    cleaned = _HORIZONTAL_SPACE_RE.sub(" ", cleaned)
    cleaned = _EXCESS_BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def clean_model_text(title: str, body: str) -> str:
    title = fix_mojibake(title or "")
    body = clean_body(body)
    model_text = build_model_text(title, body)
    model_text = _EXCESS_BLANK_RE.sub("\n\n", model_text)
    return model_text.strip()


def raw_text(row: dict[str, str]) -> str:
    return f"{row.get('title') or ''} {row.get('body') or ''}".strip()


def truncate(text: str, limit: int = EXAMPLE_TEXT_LIMIT) -> str:
    text = text.replace("\r\n", "\n")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def row_counts_by_class(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row.get("final_label") or "") for row in rows)
    return dict(sorted(counts.items()))


def split_report(
    split: str,
    original_had_model_text: bool,
    rows: list[dict[str, Any]],
    raw_lengths: list[int],
    cleaned_lengths: list[int],
) -> dict[str, Any]:
    total = len(rows)
    return {
        "split": split,
        "original_had_model_text": original_had_model_text,
        "row_count": total,
        "row_counts_by_class": row_counts_by_class(rows),
        "non_ascii_count": sum(1 for row in rows if row["has_non_ascii"] == "True"),
        "mostly_non_ascii_count": sum(
            1 for row in rows if row["mostly_non_ascii_candidate"] == "True"
        ),
        "empty_model_text_count": sum(1 for row in rows if row["empty_body"] == "True"),
        "average_raw_length": round(sum(raw_lengths) / total, 2) if total else 0,
        "average_cleaned_model_text_length": round(sum(cleaned_lengths) / total, 2)
        if total
        else 0,
    }


def process_split(
    split: str,
    examples: list[dict[str, Any]],
) -> dict[str, Any]:
    input_path = INPUT_DIR / f"{split}.csv"
    output_path = OUTPUT_DIR / f"{split}.csv"
    rows, original_fieldnames = read_csv(input_path)
    original_had_model_text = "model_text" in original_fieldnames
    output_fieldnames = [
        *original_fieldnames,
        *[
            column
            for column in ("model_text", *QUALITY_COLUMNS)
            if column not in original_fieldnames
        ],
    ]

    raw_lengths: list[int] = []
    cleaned_lengths: list[int] = []
    cleaned_rows: list[dict[str, Any]] = []
    for row in rows:
        before = raw_text(row)
        model_text = clean_model_text(row.get("title") or "", row.get("body") or "")
        flags = text_quality_flags(model_text)
        raw_lengths.append(len(before))
        cleaned_lengths.append(len(model_text))

        cleaned_row: dict[str, Any] = dict(row)
        cleaned_row["model_text"] = model_text
        for column in QUALITY_COLUMNS:
            cleaned_row[column] = str(flags[column])
        cleaned_rows.append(cleaned_row)

        if len(examples) < EXAMPLE_LIMIT and before != model_text:
            examples.append(
                {
                    "split": split,
                    "issue_number": row.get("issue_number") or "",
                    "final_label": row.get("final_label") or "",
                    "before": truncate(before),
                    "after": truncate(model_text),
                }
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return split_report(
        split,
        original_had_model_text,
        cleaned_rows,
        raw_lengths,
        cleaned_lengths,
    )


def write_examples(examples: list[dict[str, Any]]) -> None:
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXAMPLES_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["split", "issue_number", "final_label", "before", "after"],
        )
        writer.writeheader()
        writer.writerows(examples)


def main() -> int:
    for split in SPLITS:
        input_path = INPUT_DIR / f"{split}.csv"
        if not input_path.exists():
            print(f"ERROR: {input_path} not found.")
            return 1

    examples: list[dict[str, Any]] = []
    split_reports = [process_split(split, examples) for split in SPLITS]
    write_examples(examples)

    report = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "input_dir": str(INPUT_DIR),
        "output_dir": str(OUTPUT_DIR),
        "raw_processed_splits_preserved": True,
        "original_processed_csvs_already_had_model_text": {
            item["split"]: item["original_had_model_text"] for item in split_reports
        },
        "splits": split_reports,
        "cleaning_examples_path": str(EXAMPLES_PATH),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"cleaned_dir: {OUTPUT_DIR}")
    print(f"report: {REPORT_PATH}")
    print(f"examples: {EXAMPLES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
