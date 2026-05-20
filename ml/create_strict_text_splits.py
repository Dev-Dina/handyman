"""
Create strict classifier text splits from official processed splits.

Reads:   data/processed/{train,val,test}.csv
Writes:  data/processed_strict_text/{train,val,test}.csv
         reports/experiments/strict_text/strict_text_audit_report.json
         reports/experiments/strict_text/strict_text_examples.csv

Strict text rules:
  - Title weighted 2x (TITLE: <title> repeated)
  - Section filtering: keep signal sections, skip environment/template noise
  - Normalize: URLs -> <URL>, markdown images -> <IMAGE>, mentions -> <USER>
  - Preserve: commands, YAML, errors, paths, versions, code blocks
  - Preserve all original CSV columns; add strict_model_text + quality flags
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

INPUT_TRAIN = Path("data/processed/train.csv")
INPUT_VAL = Path("data/processed/val.csv")
INPUT_TEST = Path("data/processed/test.csv")

OUT_DIR = Path("data/processed_strict_text")
REPORTS_DIR = Path("reports/experiments/strict_text")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_IMAGE_RE = re.compile(r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@[A-Za-z0-9_\-]+")
_HORIZONTAL_WS_RE = re.compile(r"[ \t]+")
_SECTION_SPLIT_RE = re.compile(r"^###\s*(.+)$", re.MULTILINE)
_HEADING_MARKER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-퟿]")

# Sections to drop entirely (environment / template noise)
_SKIP_PATS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"kubernetes version",
        r"cloud provider",
        r"\bos\b",
        r"install tool",
        r"container runtime",
        r"related plugin",
        r"\benvironment\b",
        r"runtime version",
        r"hardware configuration",
        r"\bkernel\b",
        r"which os",
        r"cri version",
    ]
]


# ---------------------------------------------------------------------------
# Core text builder
# ---------------------------------------------------------------------------


def _parse_sections(body: str) -> list[tuple[str, str]]:
    """Split body on ### headings → list of (heading, content)."""
    parts = _SECTION_SPLIT_RE.split(body)
    result: list[tuple[str, str]] = []
    if parts[0].strip():
        result.append(("", parts[0]))
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""
        result.append((heading, content))
    return result


def _skip_section(heading: str) -> bool:
    for pat in _SKIP_PATS:
        if pat.search(heading):
            return True
    return False


def build_strict_model_text(title: str, body: str) -> str:
    """Build classifier-focused text with title weighting and section filtering."""
    # Normalize markdown images before URL normalization (images embed URLs)
    body = _IMAGE_RE.sub("<IMAGE>", body)
    title_clean = _HORIZONTAL_WS_RE.sub(" ", title.strip())

    parts: list[str] = [
        f"TITLE: {title_clean}",
        f"TITLE: {title_clean}",
    ]

    sections = _parse_sections(body)
    for heading, content in sections:
        if _skip_section(heading):
            continue
        # Strip heading markers from sub-headings within kept sections
        content = _HEADING_MARKER_RE.sub("", content).strip()
        if content:
            parts.append(content)

    combined = "\n".join(parts)
    combined = _URL_RE.sub("<URL>", combined)
    combined = _MENTION_RE.sub("<USER>", combined)
    combined = _HORIZONTAL_WS_RE.sub(" ", combined)
    return combined.strip()


def _quality_flags(strict_text: str, raw_text: str) -> dict:
    n = len(strict_text)
    non_ascii = sum(1 for c in strict_text if ord(c) > 127)
    ratio = non_ascii / n if n else 0.0
    return {
        "has_cjk": bool(_CJK_RE.search(strict_text)),
        "non_ascii_ratio": round(ratio, 4),
        "strict_text_length": n,
        "raw_text_length": len(raw_text),
    }


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

_NEW_COLS = [
    "strict_model_text",
    "has_cjk",
    "non_ascii_ratio",
    "strict_text_length",
    "raw_text_length",
]


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _enrich(rows: list[dict]) -> list[dict]:
    for row in rows:
        title = row.get("title") or ""
        body = row.get("body") or ""
        raw_text = f"{title} {body}"
        strict = build_strict_model_text(title, body)
        flags = _quality_flags(strict, raw_text)
        row["strict_model_text"] = strict
        row.update(flags)
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    base_fields = [k for k in rows[0] if k not in _NEW_COLS]
    fieldnames = base_fields + _NEW_COLS
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------


def _split_stats(rows: list[dict], split_name: str) -> dict:
    strict_lens = [int(r.get("strict_text_length", 0)) for r in rows]
    raw_lens = [int(r.get("raw_text_length", 0)) for r in rows]
    n = len(rows)
    avg_strict = round(sum(strict_lens) / n, 1) if n else 0.0
    avg_raw = round(sum(raw_lens) / n, 1) if n else 0.0
    cjk_count = sum(
        1 for r in rows if r.get("has_cjk") is True or r.get("has_cjk") == "True"
    )
    high_non_ascii = sum(1 for r in rows if float(r.get("non_ascii_ratio", 0)) >= 0.30)
    compression = round(avg_strict / avg_raw, 4) if avg_raw else 0.0
    per_class: dict[str, int] = defaultdict(int)
    for r in rows:
        per_class[str(r.get("final_label", ""))] += 1
    return {
        "split": split_name,
        "total_rows": n,
        "avg_strict_text_length": avg_strict,
        "avg_raw_text_length": avg_raw,
        "compression_ratio": compression,
        "has_cjk_count": cjk_count,
        "high_non_ascii_count": high_non_ascii,
        "per_class": dict(per_class),
    }


def _examples_rows(test_rows: list[dict], n_per_class: int = 3) -> list[dict]:
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in test_rows:
        by_class[str(r.get("final_label", ""))].append(r)
    examples = []
    for cls in sorted(by_class):
        for r in by_class[cls][:n_per_class]:
            examples.append(
                {
                    "issue_number": r.get("issue_number", ""),
                    "final_label": r.get("final_label", ""),
                    "title": (r.get("title") or "")[:120],
                    "strict_text_length": r.get("strict_text_length", ""),
                    "raw_text_length": r.get("raw_text_length", ""),
                    "has_cjk": r.get("has_cjk", ""),
                    "non_ascii_ratio": r.get("non_ascii_ratio", ""),
                    "strict_model_text_preview": (r.get("strict_model_text") or "")[
                        :500
                    ],
                }
            )
    return examples


def _write_examples_csv(examples: list[dict], path: Path) -> None:
    fields = [
        "issue_number",
        "final_label",
        "title",
        "strict_text_length",
        "raw_text_length",
        "has_cjk",
        "non_ascii_ratio",
        "strict_model_text_preview",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(examples)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    for path in (INPUT_TRAIN, INPUT_VAL, INPUT_TEST):
        if not path.exists():
            print(f"ERROR: {path} not found.", file=sys.stderr)
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    train_rows = _enrich(_read_csv(INPUT_TRAIN))
    val_rows = _enrich(_read_csv(INPUT_VAL))
    test_rows = _enrich(_read_csv(INPUT_TEST))

    _write_csv(train_rows, OUT_DIR / "train.csv")
    _write_csv(val_rows, OUT_DIR / "val.csv")
    _write_csv(test_rows, OUT_DIR / "test.csv")

    stats = [
        _split_stats(train_rows, "train"),
        _split_stats(val_rows, "val"),
        _split_stats(test_rows, "test"),
    ]
    report = {
        "generated_at": __import__("datetime")
        .datetime.now(tz=__import__("datetime").timezone.utc)
        .isoformat(),
        "input_paths": {
            "train": str(INPUT_TRAIN),
            "val": str(INPUT_VAL),
            "test": str(INPUT_TEST),
        },
        "output_dir": str(OUT_DIR),
        "strict_text_rules": [
            "title weighted 2x (TITLE: prefix, repeated)",
            "section filtering: skip environment/OS/runtime sections",
            "normalize URLs -> <URL>",
            "normalize markdown images -> <IMAGE>",
            "normalize GitHub mentions -> <USER>",
            "strip ### heading markers from content",
            "preserve commands, YAML, errors, paths, versions",
        ],
        "splits": stats,
    }

    (REPORTS_DIR / "strict_text_audit_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    examples = _examples_rows(test_rows)
    _write_examples_csv(examples, REPORTS_DIR / "strict_text_examples.csv")

    for s in stats:
        print(
            f"{s['split']}: rows={s['total_rows']}"
            f"  avg_strict={s['avg_strict_text_length']}"
            f"  avg_raw={s['avg_raw_text_length']}"
            f"  compression={s['compression_ratio']}"
            f"  cjk={s['has_cjk_count']}"
        )
    print(f"splits written to {OUT_DIR}/")
    print(f"audit report: {REPORTS_DIR / 'strict_text_audit_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
