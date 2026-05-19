"""
Build stratified time-based train/val/test splits from fetched Kubernetes issues.

Multi-label conflict policy:
  Issues with exactly one target label  → assigned directly (no conflict).
  Issues with multiple target labels    → deterministic priority resolution:
    bug > docs > feature > question
  All conflicts are recorded in reports/multilabel_conflicts.csv so they
  are transparent and auditable rather than silently dropped or hidden.

Split strategy:
  Per class, sort by created_at ascending.
  Oldest 70% → train, next 15% → val, newest 15% → test.
  This guarantees test is strictly newer than train within every class.

Class cap (--max-per-class):
  If set, only the oldest N issues per class are kept after conflict resolution.
  Applied before splitting so time-ordering is preserved.

Usage:
    uv run python ml/split_dataset.py
    uv run python ml/split_dataset.py --val-frac 0.15 --test-frac 0.15
    uv run python ml/split_dataset.py --max-per-class 600
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

INPUT_PATH = Path("data/raw/kubernetes_issues.jsonl")
OUTPUT_DIR = Path("data/processed")
LABELED_PATH = Path("data/processed/labeled_issues.csv")
REPORT_PATH = Path("reports/split_report.json")
CONFLICTS_PATH = Path("reports/multilabel_conflicts.csv")

# GitHub label → supervised class
TARGET_LABELS: dict[str, str] = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}

# Conflict resolution: lower index wins
_CONFLICT_PRIORITY: dict[str, int] = {
    "bug": 0,
    "docs": 1,
    "feature": 2,
    "question": 3,
}

_CSV_FIELDS = [
    "issue_number",
    "title",
    "body",
    "final_label",
    "raw_labels",
    "created_at",
    "closed_at",
    "html_url",
]

_CONFLICT_FIELDS = [
    "issue_number",
    "title",
    "target_labels_found",
    "chosen_final_label",
    "resolution_reason",
    "html_url",
]


def _resolve_label(
    raw_labels: list[str],
) -> tuple[str | None, list[str], str]:
    """Return (final_label, sorted_target_classes, resolution_reason).

    Returns (None, [], 'no_target_label') when no target label is present.
    """
    unique_classes = sorted(
        {TARGET_LABELS[lbl] for lbl in raw_labels if lbl in TARGET_LABELS},
        key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
    )
    if not unique_classes:
        return None, [], "no_target_label"
    if len(unique_classes) == 1:
        return unique_classes[0], unique_classes, "single_target_label"
    chosen = unique_classes[0]
    reason = "conflict_resolved_priority:" + "+".join(unique_classes)
    return chosen, unique_classes, reason


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def _sha256_prefix(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _write_csv(records: list[dict], path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _apply_class_cap(
    labeled: list[dict],
    max_per_class: int,
) -> tuple[list[dict], dict[str, int], dict[str, int]]:
    """Keep oldest max_per_class issues per final_label, sorted by created_at.

    Returns (capped_records, counts_before, counts_after).
    """
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in labeled:
        by_label[r["final_label"]].append(r)

    counts_before = {cls: len(rows) for cls, rows in by_label.items()}
    capped: list[dict] = []
    counts_after: dict[str, int] = {}

    for cls, rows in by_label.items():
        rows.sort(key=lambda r: r.get("created_at") or "")
        kept = rows[:max_per_class]
        capped.extend(kept)
        counts_after[cls] = len(kept)

    return capped, counts_before, counts_after


def _make_splits(
    records: list[dict],
    val_frac: float,
    test_frac: float,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Per-class chronological stratified split.

    Within each class: oldest 70% → train, next 15% → val, newest 15% → test.
    Test is newer than train within each class, preserving all four classes for
    macro-F1 and per-class F1 evaluation. Global temporal order is not guaranteed.
    See split_note in the report.
    """
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_label[r["final_label"]].append(r)

    train_all: list[dict] = []
    val_all: list[dict] = []
    test_all: list[dict] = []

    for group in by_label.values():
        group.sort(key=lambda r: r.get("created_at") or "")
        n = len(group)
        n_test = max(1, round(n * test_frac))
        n_val = max(1, round(n * val_frac))
        n_train = n - n_val - n_test

        if n_train < 1:
            train_all.extend(group[:1])
            val_all.extend(group[1:2])
            test_all.extend(group[2:])
        else:
            train_all.extend(group[:n_train])
            val_all.extend(group[n_train : n_train + n_val])
            test_all.extend(group[n_train + n_val :])

    return train_all, val_all, test_all


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build stratified time-based splits.")
    p.add_argument("--input", type=Path, default=INPUT_PATH)
    p.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    p.add_argument("--report", type=Path, default=REPORT_PATH)
    p.add_argument("--conflicts", type=Path, default=CONFLICTS_PATH)
    p.add_argument("--val-frac", type=float, default=0.15)
    p.add_argument("--test-frac", type=float, default=0.15)
    p.add_argument(
        "--max-per-class",
        type=int,
        default=None,
        help="cap each class to oldest N issues before splitting (default: no cap)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(
            f"ERROR: {args.input} not found. Run ml/fetch_dataset.py first.",
            file=sys.stderr,
        )
        return 1

    raw = _load_jsonl(args.input)
    src_hash = _sha256_prefix(args.input)

    labeled: list[dict] = []
    conflicts: list[dict] = []
    dropped = 0

    for record in raw:
        raw_labels: list[str] = record.get("raw_labels", [])
        final_label, target_classes, reason = _resolve_label(raw_labels)

        if final_label is None:
            dropped += 1
            continue

        labeled.append(
            {
                **record,
                "final_label": final_label,
                "raw_labels": "|".join(raw_labels),
            }
        )

        if len(target_classes) > 1:
            conflicts.append(
                {
                    "issue_number": record["issue_number"],
                    "title": (record.get("title") or "")[:120],
                    "target_labels_found": "|".join(target_classes),
                    "chosen_final_label": final_label,
                    "resolution_reason": reason,
                    "html_url": record.get("html_url", ""),
                }
            )

    if not labeled:
        print(
            "ERROR: no labeled issues after mapping. Check label mapping.",
            file=sys.stderr,
        )
        return 1

    # Save all labeled issues pre-cap (full picture)
    _write_csv(labeled, LABELED_PATH, _CSV_FIELDS)

    # Save conflict report (transparent, not hidden)
    _write_csv(conflicts, args.conflicts, _CONFLICT_FIELDS)

    counts_before_cap = dict(Counter(r["final_label"] for r in labeled))
    counts_after_cap: dict[str, int] | None = None

    # Apply optional per-class cap
    if args.max_per_class is not None:
        labeled, counts_before_cap, counts_after_cap = _apply_class_cap(
            labeled, args.max_per_class
        )

    train, val, test = _make_splits(labeled, args.val_frac, args.test_frac)

    _write_csv(train, args.output_dir / "train.csv", _CSV_FIELDS)
    _write_csv(val, args.output_dir / "val.csv", _CSV_FIELDS)
    _write_csv(test, args.output_dir / "test.csv", _CSV_FIELDS)

    # Global temporal check
    train_dates = [r["created_at"] for r in train if r.get("created_at")]
    test_dates = [r["created_at"] for r in test if r.get("created_at")]
    newest_train = max(train_dates) if train_dates else ""
    oldest_test = min(test_dates) if test_dates else ""
    temporal_ok: bool | None = (
        newest_train <= oldest_test if newest_train and oldest_test else None
    )

    # Per-class temporal check
    all_classes = sorted({r["final_label"] for r in labeled})
    per_class_temporal: dict[str, bool | None] = {}
    for cls in all_classes:
        cls_train = [
            r["created_at"]
            for r in train
            if r.get("final_label") == cls and r.get("created_at")
        ]
        cls_test = [
            r["created_at"]
            for r in test
            if r.get("final_label") == cls and r.get("created_at")
        ]
        if cls_train and cls_test:
            per_class_temporal[cls] = max(cls_train) <= min(cls_test)
        else:
            per_class_temporal[cls] = None


    # Conflict combinations summary
    conflict_combos: Counter = Counter()
    for c in conflicts:
        combo = tuple(sorted(c["target_labels_found"].split("|")))
        conflict_combos[combo] += 1

    report: dict = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source_hash": src_hash,
        "raw_issues": len(raw),
        "dropped_unmapped": dropped,
        "labeled_total": len(labeled),
        "class_cap": args.max_per_class,
        "class_counts_before_cap": counts_before_cap,
        "class_counts_after_cap": counts_after_cap,
        "multi_target_conflicts": len(conflicts),
        "conflict_policy": "bug > docs > feature > question",
        "conflict_combinations": [
            {"classes": list(combo), "count": cnt}
            for combo, cnt in conflict_combos.most_common()
        ],
        "conflict_examples": conflicts[:10],
        "train_count": len(train),
        "val_count": len(val),
        "test_count": len(test),
        "train_class_counts": dict(Counter(r["final_label"] for r in train)),
        "val_class_counts": dict(Counter(r["final_label"] for r in val)),
        "test_class_counts": dict(Counter(r["final_label"] for r in test)),
        "newest_train_date": newest_train,
        "oldest_test_date": oldest_test,
        "temporal_order_ok": temporal_ok,
        "per_class_temporal_ok": per_class_temporal,
        "split_note": (
            "Per-class chronological stratification is used intentionally. "
            "A strict global chronological split caused the docs class to disappear "
            "from validation/test because all docs issues predate the global val/test cutoff. "
            "Per-class split preserves all four classes for macro-F1 and per-class F1 evaluation. "
            "Test examples are newer than train examples within each class, but not globally newer across all classes."
        ),
        "val_frac": args.val_frac,
        "test_frac": args.test_frac,
        "target_label_mapping": TARGET_LABELS,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        f"raw={len(raw)} labeled_total={len(labeled)} "
        f"dropped={dropped} conflicts={len(conflicts)}"
    )
    if args.max_per_class is not None:
        print(f"class_cap={args.max_per_class}")
        print(f"counts_before_cap={counts_before_cap}")
        print(f"counts_after_cap={counts_after_cap}")
    print(f"train={len(train)} val={len(val)} test={len(test)}")
    print(f"train_class_counts={dict(Counter(r['final_label'] for r in train))}")
    print(f"val_class_counts={dict(Counter(r['final_label'] for r in val))}")
    print(f"test_class_counts={dict(Counter(r['final_label'] for r in test))}")
    print(f"temporal_order_ok={temporal_ok}")
    print(f"per_class_temporal_ok={per_class_temporal}")
    print(f"conflicts: {args.conflicts}  report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
