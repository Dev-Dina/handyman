"""
Label EDA for the fetched Kubernetes issues dataset.

Run after ml/fetch_dataset.py:
    uv run python ml/eda_labels.py

Reads:  data/raw/kubernetes_issues.jsonl
Writes:
    reports/label_eda.json
    reports/label_counts.csv
    reports/label_cooccurrence.csv
    reports/unlabeled_issues_sample.csv
    reports/multilabel_issues_sample.csv
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

INPUT_PATH = Path("data/raw/kubernetes_issues.jsonl")
REPORTS_DIR = Path("reports")

# Same mapping as split_dataset.py — kept here so EDA is self-contained
TARGET_LABELS: dict[str, str] = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}

# Conflict resolution priority (lower index = higher priority)
_CONFLICT_PRIORITY: dict[str, int] = {
    "bug": 0,
    "docs": 1,
    "feature": 2,
    "question": 3,
}


def _target_classes(raw_labels: list[str]) -> list[str]:
    return list(
        dict.fromkeys(TARGET_LABELS[lbl] for lbl in raw_labels if lbl in TARGET_LABELS)
    )


def _resolve(raw_labels: list[str]) -> str | None:
    classes = sorted(
        set(_target_classes(raw_labels)), key=lambda c: _CONFLICT_PRIORITY.get(c, 99)
    )
    return classes[0] if classes else None


def main() -> int:
    if not INPUT_PATH.exists():
        print(
            f"ERROR: {INPUT_PATH} not found. Run ml/fetch_dataset.py first.",
            file=sys.stderr,
        )
        return 1

    issues = [json.loads(line) for line in INPUT_PATH.open(encoding="utf-8")]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / ".gitkeep").touch(exist_ok=True)

    total = len(issues)
    all_raw_labels = [lbl for i in issues for lbl in i.get("raw_labels", [])]
    label_counts = Counter(all_raw_labels)

    # Classify each issue
    unlabeled: list[dict] = []
    single_class: list[dict] = []
    multi_class: list[dict] = []

    for issue in issues:
        classes = _target_classes(issue.get("raw_labels", []))
        unique = sorted(set(classes), key=lambda c: _CONFLICT_PRIORITY.get(c, 99))
        if not unique:
            unlabeled.append(issue)
        elif len(unique) == 1:
            single_class.append(issue)
        else:
            multi_class.append(issue)

    # Class counts before resolution (each target class counted independently)
    class_counts_raw: Counter = Counter()
    for issue in issues:
        for cls in set(_target_classes(issue.get("raw_labels", []))):
            class_counts_raw[cls] += 1

    # Class counts after conflict resolution
    class_counts_resolved: Counter = Counter()
    for issue in issues:
        cls = _resolve(issue.get("raw_labels", []))
        if cls:
            class_counts_resolved[cls] += 1

    # Label co-occurrence
    cooccur: Counter = Counter()
    for issue in issues:
        lbls = sorted(set(issue.get("raw_labels", [])))
        for pair in combinations(lbls, 2):
            cooccur[pair] += 1

    # Conflict combinations
    conflict_combos: Counter = Counter()
    for issue in multi_class:
        combo = tuple(
            sorted(
                set(_target_classes(issue.get("raw_labels", []))),
                key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
            )
        )
        conflict_combos[combo] += 1

    # Date range
    dates = sorted(i.get("created_at", "")[:7] for i in issues if i.get("created_at"))

    # ── write reports ──────────────────────────────────────────────────────────

    with (REPORTS_DIR / "label_counts.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "label", "count"])
        writer.writeheader()
        writer.writerows(
            {"rank": i + 1, "label": lbl, "count": cnt}
            for i, (lbl, cnt) in enumerate(label_counts.most_common())
        )

    with (REPORTS_DIR / "label_cooccurrence.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=["label_a", "label_b", "count"])
        writer.writeheader()
        writer.writerows(
            {"label_a": a, "label_b": b, "count": cnt}
            for (a, b), cnt in cooccur.most_common(50)
        )

    with (REPORTS_DIR / "unlabeled_issues_sample.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_number",
                "title",
                "raw_labels",
                "created_at",
                "html_url",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                "issue_number": i["issue_number"],
                "title": (i.get("title") or "")[:120],
                "raw_labels": "|".join(i.get("raw_labels", [])),
                "created_at": i.get("created_at", ""),
                "html_url": i.get("html_url", ""),
            }
            for i in unlabeled[:100]
        )

    with (REPORTS_DIR / "multilabel_issues_sample.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "issue_number",
                "title",
                "raw_labels",
                "target_classes",
                "created_at",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                "issue_number": i["issue_number"],
                "title": (i.get("title") or "")[:120],
                "raw_labels": "|".join(i.get("raw_labels", [])),
                "target_classes": "|".join(
                    sorted(
                        set(_target_classes(i.get("raw_labels", []))),
                        key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
                    )
                ),
                "created_at": i.get("created_at", ""),
            }
            for i in multi_class[:100]
        )

    report: dict = {
        "total_issues": total,
        "unlabeled_count": len(unlabeled),
        "single_class_count": len(single_class),
        "multi_class_conflict_count": len(multi_class),
        "class_counts_before_resolution": dict(class_counts_raw),
        "class_counts_after_resolution": dict(class_counts_resolved),
        "unique_raw_labels": len(label_counts),
        "top30_raw_labels": [
            {"label": lbl, "count": cnt} for lbl, cnt in label_counts.most_common(30)
        ],
        "top20_cooccurrences": [
            {"label_a": a, "label_b": b, "count": cnt}
            for (a, b), cnt in cooccur.most_common(20)
        ],
        "conflict_combinations": [
            {"classes": list(combo), "count": cnt}
            for combo, cnt in conflict_combos.most_common(10)
        ],
        "date_range_start": dates[0] if dates else None,
        "date_range_end": dates[-1] if dates else None,
        "months_covered": len(set(dates)),
        "target_label_mapping": TARGET_LABELS,
        "conflict_priority": list(_CONFLICT_PRIORITY.keys()),
    }
    (REPORTS_DIR / "label_eda.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"total={total}  single_class={len(single_class)}  "
        f"conflicts={len(multi_class)}  unlabeled={len(unlabeled)}"
    )
    print(f"class_counts_before_resolution: {dict(class_counts_raw)}")
    print(f"class_counts_after_resolution:  {dict(class_counts_resolved)}")
    print(
        f"date_range: {dates[0] if dates else 'N/A'} to {dates[-1] if dates else 'N/A'}"
    )
    print(f"reports saved to {REPORTS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
