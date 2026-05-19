"""
Label EDA for the fetched Kubernetes issues dataset.

Run after ml/fetch_dataset.py:
    uv run python ml/eda_labels.py

Reads:  data/raw/kubernetes_issues.jsonl
Writes:
    reports/kubernetes_label_eda.json
    reports/kubernetes_label_counts.csv
    reports/kubernetes_label_cooccurrence.csv
    reports/kubernetes_multilabel_conflicts.csv
    reports/kubernetes_class_balance_before_split.csv
    reports/unlabeled_issues_sample.csv
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

INPUT_PATH = Path("data/raw/kubernetes_issues.jsonl")
REPORTS_DIR = Path("reports")

TARGET_LABELS: dict[str, str] = {
    "kind/bug": "bug",
    "kind/feature": "feature",
    "kind/documentation": "docs",
    "kind/support": "question",
}

_CONFLICT_PRIORITY: dict[str, int] = {
    "bug": 0,
    "docs": 1,
    "feature": 2,
    "question": 3,
}

_ALL_CLASSES = ["bug", "docs", "feature", "question"]

# GitHub label that maps to "question" class
_SUPPORT_LABEL = "kind/support"


def _target_classes(raw_labels: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for lbl in raw_labels:
        if lbl in TARGET_LABELS:
            seen[TARGET_LABELS[lbl]] = None
    return list(seen)


def _resolve(raw_labels: list[str]) -> str | None:
    classes = sorted(
        set(_target_classes(raw_labels)), key=lambda c: _CONFLICT_PRIORITY.get(c, 99)
    )
    return classes[0] if classes else None


def _write_csv(records: list[dict], path: Path, fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _proceed_to_split(
    class_counts: Counter,
    total: int,
    usable: int,
    conflict_count: int,
) -> bool:
    if total == 0 or usable == 0:
        return False
    nonzero = sum(1 for c in _ALL_CLASSES if class_counts[c] > 0)
    smallest = min(class_counts[c] for c in _ALL_CLASSES)
    usable_ratio = usable / total
    conflict_ratio = conflict_count / total if total else 0
    return (
        nonzero >= 4
        and smallest >= 50
        and usable >= 200
        and usable_ratio >= 0.30
        and conflict_ratio <= 0.30
    )


def _support_stats(unique_issues: list[dict], multi_class: list[dict]) -> dict:
    """Stats specific to support/question class rebalancing."""
    support_raw = [
        i for i in unique_issues if _SUPPORT_LABEL in i.get("raw_labels", [])
    ]
    support_with_conflict = [
        i for i in multi_class if _SUPPORT_LABEL in i.get("raw_labels", [])
    ]
    support_final_question = [
        i for i in unique_issues if _resolve(i.get("raw_labels", [])) == "question"
    ]
    lost_to_conflict = len(support_raw) - len(support_final_question)
    return {
        "support_raw_count": len(support_raw),
        "support_with_target_conflict_count": len(support_with_conflict),
        "support_final_question_count": len(support_final_question),
        "support_lost_to_higher_priority": lost_to_conflict,
        "supplement_recommended": lost_to_conflict > 0,
        "supplement_suggestion": (
            f"--supplement-label kind/support --supplement-count {lost_to_conflict}"
            if lost_to_conflict > 0
            else "none needed"
        ),
    }


def main() -> int:
    if not INPUT_PATH.exists():
        print(
            f"ERROR: {INPUT_PATH} not found. Run ml/fetch_dataset.py first.",
            file=sys.stderr,
        )
        return 1

    issues = [
        json.loads(line) for line in INPUT_PATH.open(encoding="utf-8") if line.strip()
    ]
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / ".gitkeep").touch(exist_ok=True)

    total_rows = len(issues)

    # Deduplicate by issue_number
    seen_numbers: dict[int, dict] = {}
    for issue in issues:
        num = issue["issue_number"]
        if num not in seen_numbers:
            seen_numbers[num] = issue
    unique_issues = list(seen_numbers.values())
    duplicate_count = total_rows - len(unique_issues)

    # Classify each unique issue
    unlabeled: list[dict] = []
    single_class: list[dict] = []
    multi_class: list[dict] = []

    for issue in unique_issues:
        classes = list(
            dict.fromkeys(
                sorted(
                    set(_target_classes(issue.get("raw_labels", []))),
                    key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
                )
            )
        )
        if not classes:
            unlabeled.append(issue)
        elif len(classes) == 1:
            single_class.append(issue)
        else:
            multi_class.append(issue)

    # Raw GitHub label counts (across all unique issues)
    all_raw_labels = [lbl for i in unique_issues for lbl in i.get("raw_labels", [])]
    label_counts: Counter = Counter(all_raw_labels)

    # Class counts before resolution (each target class counted independently)
    class_counts_raw: Counter = Counter({c: 0 for c in _ALL_CLASSES})
    for issue in unique_issues:
        for cls in set(_target_classes(issue.get("raw_labels", []))):
            class_counts_raw[cls] += 1

    # Class counts after conflict resolution
    class_counts_resolved: Counter = Counter({c: 0 for c in _ALL_CLASSES})
    for issue in unique_issues:
        cls = _resolve(issue.get("raw_labels", []))
        if cls:
            class_counts_resolved[cls] += 1

    # Date range per class (after resolution)
    dates_by_class: dict[str, list[str]] = defaultdict(list)
    for issue in unique_issues:
        cls = _resolve(issue.get("raw_labels", []))
        dt = issue.get("created_at")
        if cls and dt:
            dates_by_class[cls].append(dt)

    date_range_per_class: dict[str, dict] = {}
    for cls in _ALL_CLASSES:
        dates = sorted(dates_by_class.get(cls, []))
        date_range_per_class[cls] = {
            "oldest": dates[0] if dates else None,
            "newest": dates[-1] if dates else None,
            "count": len(dates),
        }

    # Label co-occurrence (across unique issues)
    cooccur: Counter = Counter()
    for issue in unique_issues:
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

    # Date range overall
    all_dates = sorted(
        i.get("created_at", "")[:7] for i in unique_issues if i.get("created_at")
    )

    usable = len(single_class) + len(multi_class)
    proceed = _proceed_to_split(
        class_counts_resolved, len(unique_issues), usable, len(multi_class)
    )
    support_info = _support_stats(unique_issues, multi_class)

    # ── write reports ──────────────────────────────────────────────────────────

    _write_csv(
        [
            {"rank": i + 1, "label": lbl, "count": cnt}
            for i, (lbl, cnt) in enumerate(label_counts.most_common())
        ],
        REPORTS_DIR / "kubernetes_label_counts.csv",
        ["rank", "label", "count"],
    )

    _write_csv(
        [
            {"label_a": a, "label_b": b, "count": cnt}
            for (a, b), cnt in cooccur.most_common(50)
        ],
        REPORTS_DIR / "kubernetes_label_cooccurrence.csv",
        ["label_a", "label_b", "count"],
    )

    _write_csv(
        [
            {
                "issue_number": i["issue_number"],
                "title": (i.get("title") or "")[:120],
                "target_labels_found": "|".join(
                    sorted(
                        set(_target_classes(i.get("raw_labels", []))),
                        key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
                    )
                ),
                "chosen_final_label": _resolve(i.get("raw_labels", [])),
                "resolution_reason": "conflict_resolved_priority:"
                + "+".join(
                    sorted(
                        set(_target_classes(i.get("raw_labels", []))),
                        key=lambda c: _CONFLICT_PRIORITY.get(c, 99),
                    )
                ),
                "raw_labels": "|".join(i.get("raw_labels", [])),
                "html_url": i.get("html_url", ""),
            }
            for i in multi_class
        ],
        REPORTS_DIR / "kubernetes_multilabel_conflicts.csv",
        [
            "issue_number",
            "title",
            "target_labels_found",
            "chosen_final_label",
            "resolution_reason",
            "raw_labels",
            "html_url",
        ],
    )

    _write_csv(
        [
            {
                "class": cls,
                "count_after_resolution": class_counts_resolved[cls],
                "count_before_resolution": class_counts_raw[cls],
                "oldest_created_at": date_range_per_class[cls]["oldest"] or "",
                "newest_created_at": date_range_per_class[cls]["newest"] or "",
            }
            for cls in _ALL_CLASSES
        ],
        REPORTS_DIR / "kubernetes_class_balance_before_split.csv",
        [
            "class",
            "count_after_resolution",
            "count_before_resolution",
            "oldest_created_at",
            "newest_created_at",
        ],
    )

    _write_csv(
        [
            {
                "issue_number": i["issue_number"],
                "title": (i.get("title") or "")[:120],
                "raw_labels": "|".join(i.get("raw_labels", [])),
                "created_at": i.get("created_at", ""),
                "html_url": i.get("html_url", ""),
            }
            for i in unlabeled[:100]
        ],
        REPORTS_DIR / "unlabeled_issues_sample.csv",
        ["issue_number", "title", "raw_labels", "created_at", "html_url"],
    )

    report: dict = {
        "total_raw_rows": total_rows,
        "unique_issue_count": len(unique_issues),
        "duplicate_count": duplicate_count,
        "unlabeled_count": len(unlabeled),
        "single_class_count": len(single_class),
        "multi_class_conflict_count": len(multi_class),
        "usable_for_supervised_learning": usable,
        "class_counts_before_resolution": dict(class_counts_raw),
        "class_counts_after_resolution": dict(class_counts_resolved),
        "date_range_per_class": date_range_per_class,
        "support_question_stats": support_info,
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
        "conflict_examples": [
            {
                "issue_number": i["issue_number"],
                "title": (i.get("title") or "")[:80],
                "raw_labels": i.get("raw_labels", []),
                "chosen": _resolve(i.get("raw_labels", [])),
            }
            for i in multi_class[:10]
        ],
        "date_range_start": all_dates[0] if all_dates else None,
        "date_range_end": all_dates[-1] if all_dates else None,
        "months_covered": len(set(all_dates)),
        "target_label_mapping": TARGET_LABELS,
        "conflict_priority": list(_CONFLICT_PRIORITY.keys()),
        "proceed_to_split": proceed,
    }

    (REPORTS_DIR / "kubernetes_label_eda.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(
        f"total_rows={total_rows}  unique={len(unique_issues)}  "
        f"duplicates={duplicate_count}"
    )
    print(
        f"single_class={len(single_class)}  "
        f"conflicts={len(multi_class)}  unlabeled={len(unlabeled)}"
    )
    print(f"class_counts_before_resolution: {dict(class_counts_raw)}")
    print(f"class_counts_after_resolution:  {dict(class_counts_resolved)}")
    print(f"support_stats: {support_info}")
    print(
        f"date_range: {all_dates[0] if all_dates else 'N/A'} "
        f"to {all_dates[-1] if all_dates else 'N/A'}"
    )
    print(f"proceed_to_split: {proceed}")
    print(f"reports saved to {REPORTS_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
