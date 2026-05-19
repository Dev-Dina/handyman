"""
Light text quality checks and model_text construction for GitHub issues.

Preserves: code blocks, stack traces, kubectl/YAML/version strings, error messages.
Normalizes: whitespace, long URLs, GitHub @mentions.
Reports:    non-ASCII rows, empty body, very long rows — per split and class.

Usage (standalone audit):
    uv run python ml/text_preprocessing.py
    uv run python ml/text_preprocessing.py --drop-mostly-non-ascii

Imported by ml/finetune.py via preprocess_rows().
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TRAIN_PATH = Path("data/processed/train.csv")
VAL_PATH = Path("data/processed/val.csv")
TEST_PATH = Path("data/processed/test.csv")
REPORT_PATH = Path("reports/text_quality_report.json")

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@[A-Za-z0-9_\-]+")
_WHITESPACE_RE = re.compile(r"[ \t]+")

# Row considered "very long" above this character count (title+body combined)
_VERY_LONG_THRESHOLD = 8000
# Fraction of non-ASCII chars above which a row is a "mostly non-ASCII candidate"
_MOSTLY_NON_ASCII_RATIO = 0.30


def build_model_text(title: str, body: str) -> str:
    """Construct model_text from title + body with light normalization.

    Preserves code blocks, YAML, stack traces, version strings.
    Replaces bare long URLs with <URL> and @mentions with <USER>.
    Normalises horizontal whitespace (tabs → space, runs → single space).
    Does NOT strip newlines so code/stack-trace structure is intact.
    """
    combined = f"{title} {body}".strip()
    combined = _URL_RE.sub("<URL>", combined)
    combined = _MENTION_RE.sub("<USER>", combined)
    # Collapse runs of spaces/tabs but keep newlines
    combined = _WHITESPACE_RE.sub(" ", combined)
    return combined


def text_quality_flags(model_text: str) -> dict:
    """Return quality flags for a single model_text string."""
    total = len(model_text)
    non_ascii_chars = sum(1 for c in model_text if ord(c) > 127)
    non_ascii_ratio = non_ascii_chars / total if total > 0 else 0.0
    return {
        "has_non_ascii": non_ascii_chars > 0,
        "non_ascii_ratio": round(non_ascii_ratio, 4),
        "mostly_non_ascii_candidate": non_ascii_ratio >= _MOSTLY_NON_ASCII_RATIO,
        "empty_body": len(model_text.strip()) == 0,
        "very_long": total > _VERY_LONG_THRESHOLD,
        "char_count": total,
    }


def preprocess_rows(
    rows: list[dict],
    drop_mostly_non_ascii: bool = False,
) -> list[dict]:
    """Add model_text and quality flags to each row. Optionally drop noisy rows.

    Mutates rows in-place with new keys; returns filtered list.
    Raw title and body are never modified.
    """
    kept: list[dict] = []
    for row in rows:
        title = row.get("title") or ""
        body = row.get("body") or ""
        model_text = build_model_text(title, body)
        flags = text_quality_flags(model_text)
        row["model_text"] = model_text
        row.update(flags)

        if drop_mostly_non_ascii and flags["mostly_non_ascii_candidate"]:
            continue
        kept.append(row)
    return kept


def _split_stats(rows: list[dict], split_name: str) -> dict:
    classes = sorted({r.get("final_label", "") for r in rows})
    per_class: dict[str, dict] = {}
    for cls in classes:
        cls_rows = [r for r in rows if r.get("final_label") == cls]
        per_class[cls] = {
            "total": len(cls_rows),
            "non_ascii_rows": sum(1 for r in cls_rows if r.get("has_non_ascii")),
            "mostly_non_ascii_candidates": sum(
                1 for r in cls_rows if r.get("mostly_non_ascii_candidate")
            ),
            "empty_body_rows": sum(1 for r in cls_rows if r.get("empty_body")),
            "very_long_rows": sum(1 for r in cls_rows if r.get("very_long")),
        }
    return {
        "split": split_name,
        "total_rows": len(rows),
        "non_ascii_rows": sum(1 for r in rows if r.get("has_non_ascii")),
        "mostly_non_ascii_candidates": sum(
            1 for r in rows if r.get("mostly_non_ascii_candidate")
        ),
        "empty_body_rows": sum(1 for r in rows if r.get("empty_body")),
        "very_long_rows": sum(1 for r in rows if r.get("very_long")),
        "per_class": per_class,
    }


def build_quality_report(
    split_stats: list[dict],
    drop_mostly_non_ascii: bool,
) -> dict:
    return {
        "drop_mostly_non_ascii": drop_mostly_non_ascii,
        "mostly_non_ascii_threshold": _MOSTLY_NON_ASCII_RATIO,
        "very_long_threshold": _VERY_LONG_THRESHOLD,
        "splits": split_stats,
    }


def main() -> int:
    import argparse
    import csv

    p = argparse.ArgumentParser(description="Text quality audit for split CSVs.")
    p.add_argument(
        "--drop-mostly-non-ascii",
        action="store_true",
        default=False,
        help="Drop rows where non-ASCII ratio >= 0.30 (default: report only).",
    )
    args = p.parse_args()

    for path in (TRAIN_PATH, VAL_PATH, TEST_PATH):
        if not path.exists():
            print(
                f"ERROR: {path} not found. Run ml/split_dataset.py first.",
                file=sys.stderr,
            )
            return 1

    def read_csv(path: Path) -> list[dict]:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    train_rows = preprocess_rows(read_csv(TRAIN_PATH), args.drop_mostly_non_ascii)
    val_rows = preprocess_rows(read_csv(VAL_PATH), args.drop_mostly_non_ascii)
    test_rows = preprocess_rows(read_csv(TEST_PATH), args.drop_mostly_non_ascii)

    stats = [
        _split_stats(train_rows, "train"),
        _split_stats(val_rows, "val"),
        _split_stats(test_rows, "test"),
    ]
    report = build_quality_report(stats, args.drop_mostly_non_ascii)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for s in stats:
        print(
            f"{s['split']}: total={s['total_rows']} "
            f"non_ascii={s['non_ascii_rows']} "
            f"mostly_non_ascii={s['mostly_non_ascii_candidates']} "
            f"empty_body={s['empty_body_rows']} "
            f"very_long={s['very_long_rows']}"
        )
    print(f"report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
