"""
Generate presentation-ready EDA figures from existing Kubernetes reports.

Reads:
    reports/kubernetes_label_eda.json
    reports/text_quality_report.json
    reports/split_report.json
    reports/kubernetes_label_counts.csv
    reports/kubernetes_multilabel_conflicts.csv

Writes:
    reports/figures/01_class_counts_before_after_resolution.png
    reports/figures/02_split_class_balance.png
    reports/figures/03_top_kubernetes_labels.png
    reports/figures/04_multilabel_conflict_combinations.png
    reports/figures/05_text_quality_by_split.png
    reports/figures/06_very_long_rows_by_class.png

Usage:
    uv run python ml/make_eda_figures.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"

EDA_PATH = REPORTS_DIR / "kubernetes_label_eda.json"
TQ_PATH = REPORTS_DIR / "text_quality_report.json"
SPLIT_PATH = REPORTS_DIR / "split_report.json"
LABEL_COUNTS_PATH = REPORTS_DIR / "kubernetes_label_counts.csv"

_CLASSES = ["bug", "docs", "feature", "question"]
_COLORS = ["#4C72B0", "#DD8452", "#55A868", "#C44E52"]
_CLASS_COLORS = dict(zip(_CLASSES, _COLORS))


def _save(fig, name: str) -> None:
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  saved: {path}")


def fig_01_class_counts(eda: dict, plt) -> None:
    before = eda["class_counts_before_resolution"]
    after = eda["class_counts_after_resolution"]
    classes = _CLASSES

    import numpy as np

    x = np.arange(len(classes))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    bars_b = ax.bar(x - w / 2, [before[c] for c in classes], w,
                    label="Before resolution", color="#4C72B0", alpha=0.85)
    bars_a = ax.bar(x + w / 2, [after[c] for c in classes], w,
                    label="After resolution", color="#DD8452", alpha=0.85)

    for bar in (*bars_b, *bars_a):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                str(int(bar.get_height())), ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(classes, fontsize=11)
    ax.set_ylabel("Issue count")
    ax.set_title("Class counts before vs after multi-label conflict resolution\n"
                 "(kubernetes/kubernetes, 3923 unique issues)")
    ax.legend()
    ax.set_ylim(0, max(before[c] for c in classes) * 1.15)
    fig.tight_layout()
    _save(fig, "01_class_counts_before_after_resolution.png")
    plt.close(fig)


def fig_02_split_class_balance(sr: dict, plt) -> None:
    splits = {
        "train": sr["train_class_counts"],
        "val": sr["val_class_counts"],
        "test": sr["test_class_counts"],
    }
    import numpy as np

    x = np.arange(len(_CLASSES))
    w = 0.25
    offsets = [-w, 0, w]
    split_colors = ["#4C72B0", "#55A868", "#C44E52"]

    fig, ax = plt.subplots(figsize=(9, 5))
    for (split_name, counts), offset, color in zip(splits.items(), offsets, split_colors):
        vals = [counts.get(c, 0) for c in _CLASSES]
        bars = ax.bar(x + offset, vals, w, label=split_name, color=color, alpha=0.85)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                    str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(_CLASSES, fontsize=11)
    ax.set_ylabel("Issue count")
    ax.set_title("Per-class counts per split\n"
                 f"(cap={sr['class_cap']}/class · train={sr['train_count']} "
                 f"val={sr['val_count']} test={sr['test_count']})")
    ax.legend()
    ax.set_ylim(0, max(sr["train_class_counts"].get(c, 0) for c in _CLASSES) * 1.20)
    fig.tight_layout()
    _save(fig, "02_split_class_balance.png")
    plt.close(fig)


def fig_03_top_labels(label_rows: list[dict], plt) -> None:
    top = label_rows[:20]
    labels = [r["label"] for r in top]
    counts = [int(r["count"]) for r in top]

    target_set = {"kind/bug", "kind/feature", "kind/documentation", "kind/support"}
    colors = ["#C44E52" if lbl in target_set else "#4C72B0" for lbl in labels]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(labels[::-1], counts[::-1], color=colors[::-1], alpha=0.85)
    for bar in bars:
        ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height() / 2,
                str(int(bar.get_width())), va="center", fontsize=8)

    ax.set_xlabel("Occurrence count")
    ax.set_title("Top 20 GitHub labels in the dataset\n"
                 "(red = target labels used for classification)")
    ax.set_xlim(0, max(counts) * 1.12)
    fig.tight_layout()
    _save(fig, "03_top_kubernetes_labels.png")
    plt.close(fig)


def fig_04_conflict_combinations(eda: dict, plt) -> None:
    combos = eda["conflict_combinations"][:10]
    labels = ["+".join(c["classes"]) for c in combos]
    counts = [c["count"] for c in combos]
    total_conflicts = eda["multi_class_conflict_count"]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(range(len(labels)), counts, color="#DD8452", alpha=0.85)
    for bar, cnt in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                str(cnt), ha="center", va="bottom", fontsize=9)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=10)
    ax.set_ylabel("Count")
    ax.set_title(f"Multi-label conflict combinations (total={total_conflicts})\n"
                 "Policy: bug > docs > feature > question")
    ax.set_ylim(0, max(counts) * 1.15)
    fig.tight_layout()
    _save(fig, "04_multilabel_conflict_combinations.png")
    plt.close(fig)


def fig_05_text_quality_by_split(tq: dict, plt) -> None:
    splits_data = {s["split"]: s for s in tq["splits"]}
    split_names = ["train", "val", "test"]
    metrics = ["non_ascii_rows", "mostly_non_ascii_candidates",
               "empty_body_rows", "very_long_rows"]
    metric_labels = ["Non-ASCII rows", "Mostly non-ASCII\ncandidates",
                     "Empty body", "Very long rows\n(>8000 chars)"]

    import numpy as np

    x = np.arange(len(metrics))
    w = 0.25
    offsets = [-w, 0, w]
    split_colors = ["#4C72B0", "#55A868", "#C44E52"]

    fig, ax = plt.subplots(figsize=(10, 5))
    for split_name, offset, color in zip(split_names, offsets, split_colors):
        s = splits_data.get(split_name, {})
        vals = [s.get(m, 0) for m in metrics]
        bars = ax.bar(x + offset, vals, w, label=split_name, color=color, alpha=0.85)
        for bar in bars:
            if bar.get_height() > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        str(int(bar.get_height())), ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.set_ylabel("Row count")
    ax.set_title("Text quality flags by split\n"
                 f"(mostly-non-ASCII threshold={tq['mostly_non_ascii_threshold']:.0%}  "
                 f"very-long threshold={tq['very_long_threshold']:,} chars)")
    ax.legend()
    fig.tight_layout()
    _save(fig, "05_text_quality_by_split.png")
    plt.close(fig)


def fig_06_very_long_by_class(tq: dict, plt) -> None:
    train_per_class = tq["splits"][0]["per_class"]
    classes = _CLASSES
    very_long = [train_per_class.get(c, {}).get("very_long_rows", 0) for c in classes]
    non_ascii = [train_per_class.get(c, {}).get("non_ascii_rows", 0) for c in classes]

    import numpy as np

    x = np.arange(len(classes))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    bars_vl = ax.bar(x - w / 2, very_long, w, label="Very long rows (>8000 chars)",
                     color="#C44E52", alpha=0.85)
    bars_na = ax.bar(x + w / 2, non_ascii, w, label="Non-ASCII rows",
                     color="#8172B2", alpha=0.85)

    for bar in (*bars_vl, *bars_na):
        if bar.get_height() > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    str(int(bar.get_height())), ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(classes, fontsize=11)
    ax.set_ylabel("Row count (train split)")
    ax.set_title("Very long and non-ASCII rows by class (train split only)")
    ax.legend()
    fig.tight_layout()
    _save(fig, "06_very_long_rows_by_class.png")
    plt.close(fig)


def main() -> int:
    for path in (EDA_PATH, SPLIT_PATH, LABEL_COUNTS_PATH):
        if not path.exists():
            print(f"ERROR: {path} not found.", file=sys.stderr)
            return 1

    tq_available = TQ_PATH.exists()
    if not tq_available:
        print(
            "WARNING: text_quality_report.json not found; "
            "figures 05 and 06 will be skipped.",
            file=sys.stderr,
        )

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        print(f"ERROR: matplotlib not available. {exc}", file=sys.stderr)
        return 1

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIGURES_DIR / ".gitkeep").touch(exist_ok=True)

    eda = json.loads(EDA_PATH.read_text(encoding="utf-8"))
    sr = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    label_rows = list(csv.DictReader(LABEL_COUNTS_PATH.open(encoding="utf-8")))

    plt.rcParams.update({"figure.dpi": 150, "font.size": 10})

    fig_01_class_counts(eda, plt)
    fig_02_split_class_balance(sr, plt)
    fig_03_top_labels(label_rows, plt)
    fig_04_conflict_combinations(eda, plt)

    if tq_available:
        tq = json.loads(TQ_PATH.read_text(encoding="utf-8"))
        fig_05_text_quality_by_split(tq, plt)
        fig_06_very_long_by_class(tq, plt)
    else:
        print("Skipped figures 05 and 06 (no text_quality_report.json).")

    print(f"\nAll figures saved to {FIGURES_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
