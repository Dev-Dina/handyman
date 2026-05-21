"""
Generate three-way classifier comparison artifacts.

Reads from official result files:
  reports/classical/best_classical_eval.json
  reports/transformer/codebert_base_e3_len384/transformer_eval.json
  reports/llm/llama3_full/llm_eval.json

Writes:
  reports/classifier_three_way_comparison.json
  reports/classifier_three_way_comparison.csv
  reports/official/figures/15_three_way_macro_f1.png
  reports/official/figures/16_three_way_accuracy.png
  reports/official/figures/17_three_way_question_f1.png
  reports/official/figures/18_three_way_latency.png
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from app.core.paths import PROJECT_ROOT, REPORTS_DIR
from ml.classifier_config import OFFICIAL_FIGURES_DIR

_CLASSICAL_EVAL = REPORTS_DIR / "classical" / "best_classical_eval.json"
_CODEBERT_EVAL = (
    REPORTS_DIR / "transformer" / "codebert_base_e3_len384" / "transformer_eval.json"
)
_LLM_EVAL = REPORTS_DIR / "llm" / "llama3_full" / "llm_eval.json"
_OUT_JSON = REPORTS_DIR / "classifier_three_way_comparison.json"
_OUT_CSV = REPORTS_DIR / "classifier_three_way_comparison.csv"
_FIGURES_DIR = OFFICIAL_FIGURES_DIR

_GOLD = "#E8A838"
_BLUE = "#4C72B0"
_GRAY = "#9E9E9E"

_BAR_LABELS = [
    "LogisticRegression\n(TF-IDF)",
    "CodeBERT\n(fine-tuned)",
    "Llama 3\n(zero-shot)",
]
_BAR_COLORS = [_BLUE, _GOLD, _GRAY]

_TEST_ROWS = 360


def _load() -> dict:
    classical = json.loads(_CLASSICAL_EVAL.read_text())
    codebert = json.loads(_CODEBERT_EVAL.read_text())
    llm = json.loads(_LLM_EVAL.read_text())

    classical_test = classical["test_results"]
    codebert_test = codebert["test_metrics"]
    llm_metrics = llm["metrics"]

    return {
        "classical": {
            "model": "LogisticRegression (TF-IDF)",
            "accuracy": classical_test["accuracy"],
            "macro_f1": classical_test["macro_f1"],
            "per_class_f1": {
                k: v["f1"]
                for k, v in classical_test["per_class_precision_recall_f1"].items()
            },
            "avg_latency_seconds": classical_test["predict_time_seconds"] / _TEST_ROWS,
            "deployment": "operational_fallback",
        },
        "codebert": {
            "model": "microsoft/codebert-base",
            "accuracy": codebert_test["accuracy"],
            "macro_f1": codebert_test["macro_f1"],
            "per_class_f1": {k: v["f1"] for k, v in codebert_test["per_class"].items()},
            "avg_latency_seconds": None,
            "deployment": "PRIMARY",
        },
        "llm": {
            "model": "llama3:latest (Ollama)",
            "accuracy": llm_metrics["accuracy"],
            "macro_f1": llm_metrics["macro_f1"],
            "per_class_f1": {k: v["f1"] for k, v in llm_metrics["per_class"].items()},
            "avg_latency_seconds": llm["latency"]["avg_seconds"],
            "deployment": "not_selected",
        },
    }


def _write_json(data: dict) -> None:
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "test_set": "data/processed/test.csv",
        "test_rows": _TEST_ROWS,
        "deployment_decision": {
            "primary": "microsoft/codebert-base",
            "rationale": (
                "Highest held-out test macro-F1 (0.7061) and accuracy (0.7500) "
                "across all three tracks."
            ),
            "operational_fallback": "LogisticRegression (TF-IDF)",
            "fallback_rationale": (
                "Close macro-F1 (0.6938), no GPU required, ~110k× faster inference."
            ),
            "llm_not_selected": (
                "Llama 3 has the lowest macro-F1 (0.5554) and slowest inference "
                "(24.9 s/sample) despite zero API cost."
            ),
        },
        "models": data,
    }
    _OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"wrote {_OUT_JSON.relative_to(PROJECT_ROOT)}")


def _write_csv(data: dict) -> None:
    rows = [
        {
            "track": "Classical",
            "model": data["classical"]["model"],
            "accuracy": data["classical"]["accuracy"],
            "macro_f1": data["classical"]["macro_f1"],
            "bug_f1": data["classical"]["per_class_f1"]["bug"],
            "docs_f1": data["classical"]["per_class_f1"]["docs"],
            "feature_f1": data["classical"]["per_class_f1"]["feature"],
            "question_f1": data["classical"]["per_class_f1"]["question"],
            "avg_latency_s": f"{data['classical']['avg_latency_seconds']:.6f}",
            "deployment": data["classical"]["deployment"],
        },
        {
            "track": "Transformer",
            "model": data["codebert"]["model"],
            "accuracy": data["codebert"]["accuracy"],
            "macro_f1": data["codebert"]["macro_f1"],
            "bug_f1": data["codebert"]["per_class_f1"]["bug"],
            "docs_f1": data["codebert"]["per_class_f1"]["docs"],
            "feature_f1": data["codebert"]["per_class_f1"]["feature"],
            "question_f1": data["codebert"]["per_class_f1"]["question"],
            "avg_latency_s": "N/A",
            "deployment": data["codebert"]["deployment"],
        },
        {
            "track": "LLM (zero-shot)",
            "model": data["llm"]["model"],
            "accuracy": data["llm"]["accuracy"],
            "macro_f1": data["llm"]["macro_f1"],
            "bug_f1": data["llm"]["per_class_f1"]["bug"],
            "docs_f1": data["llm"]["per_class_f1"]["docs"],
            "feature_f1": data["llm"]["per_class_f1"]["feature"],
            "question_f1": data["llm"]["per_class_f1"]["question"],
            "avg_latency_s": f"{data['llm']['avg_latency_seconds']:.1f}",
            "deployment": data["llm"]["deployment"],
        },
    ]
    with _OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {_OUT_CSV.relative_to(PROJECT_ROOT)}")


def _annotate_bars(ax: plt.Axes, bars, fmt: str = "{:.4f}") -> None:
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + ax.get_ylim()[1] * 0.01,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=9,
        )


def fig15(data: dict) -> None:
    vals = [
        data["classical"]["macro_f1"],
        data["codebert"]["macro_f1"],
        data["llm"]["macro_f1"],
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(_BAR_LABELS, vals, color=_BAR_COLORS, width=0.5, zorder=3)
    _annotate_bars(ax, bars)
    ax.set_ylim(0, 0.85)
    ax.set_ylabel("Test Macro-F1")
    ax.set_title(
        "Three-Way Classifier Comparison — Test Macro-F1\n"
        "(kubernetes/kubernetes · 360 test rows)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    winner_patch = mpatches.Patch(color=_GOLD, label="Primary deployment: CodeBERT")
    ax.legend(handles=[winner_patch], fontsize=8)
    fig.tight_layout()
    path = _FIGURES_DIR / "15_three_way_macro_f1.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def fig16(data: dict) -> None:
    vals = [
        data["classical"]["accuracy"],
        data["codebert"]["accuracy"],
        data["llm"]["accuracy"],
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(_BAR_LABELS, vals, color=_BAR_COLORS, width=0.5, zorder=3)
    _annotate_bars(ax, bars)
    ax.set_ylim(0, 0.90)
    ax.set_ylabel("Test Accuracy")
    ax.set_title(
        "Three-Way Classifier Comparison — Test Accuracy\n"
        "(kubernetes/kubernetes · 360 test rows)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    fig.tight_layout()
    path = _FIGURES_DIR / "16_three_way_accuracy.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def fig17(data: dict) -> None:
    vals = [
        data["classical"]["per_class_f1"]["question"],
        data["codebert"]["per_class_f1"]["question"],
        data["llm"]["per_class_f1"]["question"],
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(_BAR_LABELS, vals, color=_BAR_COLORS, width=0.5, zorder=3)
    _annotate_bars(ax, bars)
    ax.set_ylim(0, 0.55)
    ax.set_ylabel("Question Class F1")
    ax.set_title(
        "Three-Way Classifier Comparison — Question F1\n"
        "(hardest class across all tracks)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax.text(
        0.5,
        0.03,
        "question class: low recall in all three models",
        ha="center",
        transform=ax.transAxes,
        fontsize=8,
        color="gray",
    )
    fig.tight_layout()
    path = _FIGURES_DIR / "17_three_way_question_f1.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def fig18(data: dict) -> None:
    classical_per = data["classical"]["avg_latency_seconds"]
    llm_per = data["llm"]["avg_latency_seconds"]

    lat_labels = ["LogisticRegression\n(TF-IDF)", "Llama 3\n(zero-shot)"]
    lat_vals = [classical_per, llm_per]
    lat_colors = [_BLUE, _GRAY]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(lat_labels, lat_vals, color=lat_colors, width=0.4, zorder=3)
    for bar in bars:
        h = bar.get_height()
        label = f"{h:.5f} s" if h < 0.01 else f"{h:.1f} s"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h * 1.5,
            label,
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.set_yscale("log")
    ax.set_ylabel("Avg latency per sample (seconds, log scale)")
    ax.set_title(
        "Inference Latency per Sample\n"
        "(CodeBERT GPU latency not measured; Llama 3 via Ollama local)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    ax.text(
        0.98,
        0.97,
        "CodeBERT: GPU inference (not measured)",
        ha="right",
        va="top",
        transform=ax.transAxes,
        fontsize=8,
        color="gray",
        style="italic",
    )
    fig.tight_layout()
    path = _FIGURES_DIR / "18_three_way_latency.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"wrote {path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    _FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    data = _load()
    _write_json(data)
    _write_csv(data)
    fig15(data)
    fig16(data)
    fig17(data)
    fig18(data)
    print("done")


if __name__ == "__main__":
    main()
