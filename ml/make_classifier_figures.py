"""
Generate presentation-ready classifier figures from official results.

Reads:
    reports/classical/best_classical_eval.json
    reports/classical/classical_comparison.json
    reports/transformer/transformer_runs_summary.csv
    reports/transformer/codebert_base_e3_len384/transformer_eval.json

Writes:
    reports/official/figures/10_transformer_encoder_macro_f1.png
    reports/official/figures/11_transformer_question_f1.png
    reports/official/figures/12_classical_vs_transformer_macro_f1.png
    reports/official/figures/13_codebert_per_class_f1.png
    reports/official/figures/14_classifier_decision_summary.png

Usage:
    uv run python ml/make_classifier_figures.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ml.classifier_config import (  # noqa: E402
    CLASSICAL_TEST_MACRO_F1,
    CODEBERT_TEST_MACRO_F1,
    LABELS,
    OFFICIAL_CLASSICAL_REPORT_DIR,
    OFFICIAL_FIGURES_DIR,
    OFFICIAL_TRANSFORMER_REPORT_DIR,
)

CLASSICAL_EVAL_PATH = OFFICIAL_CLASSICAL_REPORT_DIR / "best_classical_eval.json"
CLASSICAL_COMPARISON_PATH = OFFICIAL_CLASSICAL_REPORT_DIR / "classical_comparison.json"
RUNS_SUMMARY_PATH = OFFICIAL_TRANSFORMER_REPORT_DIR / "transformer_runs_summary.csv"
CODEBERT_EVAL_PATH = (
    OFFICIAL_TRANSFORMER_REPORT_DIR
    / "codebert_base_e3_len384"
    / "transformer_eval.json"
)

_CLASSES = list(LABELS)
_BLUE = "#4C72B0"
_ORANGE = "#DD8452"
_GREEN = "#55A868"
_RED = "#C44E52"
_GOLD = "#E8A838"
_GREY = "#8E8E8E"

_RUN_DISPLAY = {
    "bert-tiny": "bert-tiny\n(29M)",
    "electra_small_e5_len384": "ELECTRA-small\n(14M)",
    "codebert_base_e3_len384": "CodeBERT\n(125M)",
    "minilm_l12_e5_len384": "MiniLM-L12\n(33M)",
}


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _annotate_bars(ax, bars, values, fmt="{:.3f}", offset_frac=0.02):
    y_max = max(values) if values else 1.0
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + y_max * offset_frac,
            fmt.format(val),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )


def fig10_transformer_macro_f1(runs: list[dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(runs, key=lambda r: float(r["test_macro_f1"]), reverse=True)
    labels = [_RUN_DISPLAY.get(r["run_name"], r["run_name"]) for r in ordered]
    scores = [float(r["test_macro_f1"]) for r in ordered]
    colors = [
        _GOLD if r["run_name"] == "codebert_base_e3_len384" else _BLUE for r in ordered
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, scores, color=colors, alpha=0.88, width=0.55)
    ax.set_ylim(0, max(scores) * 1.18)
    ax.set_ylabel("Test macro-F1", fontsize=11)
    ax.set_title(
        "Transformer Encoder Comparison — Test Macro-F1", fontsize=13, fontweight="bold"
    )
    ax.axhline(
        CLASSICAL_TEST_MACRO_F1,
        color=_RED,
        linestyle="--",
        linewidth=1.2,
        label=f"Classical baseline ({CLASSICAL_TEST_MACRO_F1:.3f})",
    )
    ax.legend(fontsize=9)
    _annotate_bars(ax, bars, scores)
    ax.tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "10_transformer_encoder_macro_f1.png", dpi=150)
    plt.close(fig)
    print("  saved: 10_transformer_encoder_macro_f1.png")


def fig11_transformer_question_f1(runs: list[dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ordered = sorted(runs, key=lambda r: float(r["question_f1"]), reverse=True)
    labels = [_RUN_DISPLAY.get(r["run_name"], r["run_name"]) for r in ordered]
    scores = [float(r["question_f1"]) for r in ordered]
    colors = [
        _GOLD if r["run_name"] == "minilm_l12_e5_len384" else _ORANGE for r in ordered
    ]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(labels, scores, color=colors, alpha=0.88, width=0.55)
    ax.set_ylim(0, max(scores) * 1.22)
    ax.set_ylabel("Test F1 — question class", fontsize=11)
    ax.set_title(
        "Transformer Encoder Comparison — Question Class F1\n(hardest class across all models)",
        fontsize=12,
        fontweight="bold",
    )
    classical_q = 0.35461
    ax.axhline(
        classical_q,
        color=_RED,
        linestyle="--",
        linewidth=1.2,
        label=f"Classical baseline ({classical_q:.3f})",
    )
    ax.legend(fontsize=9)
    _annotate_bars(ax, bars, scores)
    ax.tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "11_transformer_question_f1.png", dpi=150)
    plt.close(fig)
    print("  saved: 11_transformer_question_f1.png")


def fig12_classical_vs_transformer(out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = ["LogisticRegression\n(TF-IDF)", "CodeBERT\n(fine-tuned)"]
    scores = [CLASSICAL_TEST_MACRO_F1, CODEBERT_TEST_MACRO_F1]
    colors = [_BLUE, _GOLD]
    acc = [0.713889, 0.75]

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    bars0 = axes[0].bar(models, scores, color=colors, alpha=0.88, width=0.5)
    axes[0].set_ylim(0, max(scores) * 1.18)
    axes[0].set_ylabel("Test macro-F1", fontsize=11)
    axes[0].set_title("Test Macro-F1", fontsize=12, fontweight="bold")
    _annotate_bars(axes[0], bars0, scores)

    bars1 = axes[1].bar(models, acc, color=colors, alpha=0.88, width=0.5)
    axes[1].set_ylim(0, max(acc) * 1.18)
    axes[1].set_ylabel("Test accuracy", fontsize=11)
    axes[1].set_title("Test Accuracy", fontsize=12, fontweight="bold")
    _annotate_bars(axes[1], bars1, acc)

    for ax in axes:
        ax.tick_params(axis="x", labelsize=9)

    fig.suptitle(
        "Classical Baseline vs Best Transformer (CodeBERT)",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(out_dir / "12_classical_vs_transformer_macro_f1.png", dpi=150)
    plt.close(fig)
    print("  saved: 12_classical_vs_transformer_macro_f1.png")


def fig13_codebert_per_class(codebert_eval: dict, out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    per_class = codebert_eval["test_metrics"]["per_class"]
    classical_per_class = {
        "bug": 0.706977,
        "docs": 0.847458,
        "feature": 0.86631,
        "question": 0.35461,
    }

    classes = _CLASSES
    codebert_f1 = [per_class[c]["f1"] for c in classes]
    classical_f1 = [classical_per_class[c] for c in classes]

    x = range(len(classes))
    width = 0.38

    fig, ax = plt.subplots(figsize=(9, 5))
    bars_lr = ax.bar(
        [i - width / 2 for i in x],
        classical_f1,
        width=width,
        color=_BLUE,
        alpha=0.85,
        label="LogisticRegression (classical)",
    )
    bars_cb = ax.bar(
        [i + width / 2 for i in x],
        codebert_f1,
        width=width,
        color=_GOLD,
        alpha=0.85,
        label="CodeBERT (fine-tuned)",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(classes, fontsize=11)
    ax.set_ylim(0, max(max(codebert_f1), max(classical_f1)) * 1.18)
    ax.set_ylabel("Test F1", fontsize=11)
    ax.set_title("Per-Class F1: Classical vs CodeBERT", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    _annotate_bars(ax, bars_lr, classical_f1)
    _annotate_bars(ax, bars_cb, codebert_f1)
    fig.tight_layout()
    fig.savefig(out_dir / "13_codebert_per_class_f1.png", dpi=150)
    plt.close(fig)
    print("  saved: 13_codebert_per_class_f1.png")


def fig14_decision_summary(out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis("off")

    col_labels = [
        "Track",
        "Model",
        "test_macro_F1",
        "test_accuracy",
        "question_F1",
        "Notes",
    ]
    rows = [
        [
            "Classical",
            "LogisticRegression\n(TF-IDF, ngram 1-2)",
            "0.6938",
            "0.7139",
            "0.3546",
            "Fast, no GPU\nrequired",
        ],
        [
            "Transformer",
            "CodeBERT\n(full fine-tune, 3ep)",
            "0.7061 ★",
            "0.7500",
            "0.2909",
            "Best overall F1\n+0.012 vs classical",
        ],
        [
            "Transformer",
            "MiniLM-L12\n(full fine-tune, 5ep)",
            "0.6332",
            "0.6444",
            "0.4510 ★",
            "Best question F1\n(but worst overall)",
        ],
        [
            "LLM baseline",
            "— (pending)",
            "TODO",
            "TODO",
            "TODO",
            "Zero-shot via\nClaude API",
        ],
    ]

    row_colors = [
        ["#E8F0FE"] * 6,
        ["#FFF3CD"] * 6,
        ["#E8F4E8"] * 6,
        ["#F5F5F5"] * 6,
    ]

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
        cellColours=row_colors,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 2.2)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#CCCCCC")
        if row == 0:
            cell.set_text_props(fontweight="bold", color="white")
            cell.set_facecolor("#2C4770")
        if row == 2 and col in (2, 3):
            cell.set_text_props(fontweight="bold")

    ax.set_title(
        "Classifier Track Decision Summary\n"
        "Deployment draft: CodeBERT (best F1)  |  Alternative: Classical (no GPU, low latency)",
        fontsize=12,
        fontweight="bold",
        pad=16,
    )

    legend_handles = [
        mpatches.Patch(color="#E8F0FE", label="Classical baseline"),
        mpatches.Patch(color="#FFF3CD", label="Best transformer (deployment draft)"),
        mpatches.Patch(color="#E8F4E8", label="Best question F1 (not best overall)"),
        mpatches.Patch(color="#F5F5F5", label="Pending"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=4,
        fontsize=8,
        frameon=True,
        bbox_to_anchor=(0.5, -0.04),
    )

    fig.tight_layout()
    fig.savefig(
        out_dir / "14_classifier_decision_summary.png", dpi=150, bbox_inches="tight"
    )
    plt.close(fig)
    print("  saved: 14_classifier_decision_summary.png")


def main() -> int:
    for path in (CLASSICAL_EVAL_PATH, RUNS_SUMMARY_PATH, CODEBERT_EVAL_PATH):
        if not path.exists():
            print(f"ERROR: {path} not found.", file=sys.stderr)
            return 1

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("ERROR: matplotlib not installed.", file=sys.stderr)
        return 1

    OFFICIAL_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    (OFFICIAL_FIGURES_DIR / ".gitkeep").touch(exist_ok=True)

    runs = _read_csv(RUNS_SUMMARY_PATH)
    codebert_eval = _read_json(CODEBERT_EVAL_PATH)

    fig10_transformer_macro_f1(runs, OFFICIAL_FIGURES_DIR)
    fig11_transformer_question_f1(runs, OFFICIAL_FIGURES_DIR)
    fig12_classical_vs_transformer(OFFICIAL_FIGURES_DIR)
    fig13_codebert_per_class(codebert_eval, OFFICIAL_FIGURES_DIR)
    fig14_decision_summary(OFFICIAL_FIGURES_DIR)

    print(f"\nAll classifier figures written to: {OFFICIAL_FIGURES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
