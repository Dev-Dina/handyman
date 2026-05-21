"""Generate embedding model comparison tables from retrieval_runs_summary.csv.

Reads all dense runs, ranks by mrr_at_10 then hit_at_5, selects the best model,
and writes embedding_model_comparison.json and .csv.

Also generates hybrid_alpha_comparison.json/.csv from hybrid runs.

Usage:
    python -m pipelines.rag.make_embedding_comparison
    python -m pipelines.rag.make_embedding_comparison --output-dir reports/rag/retrieval
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.rag.config import RAG_RETRIEVAL_REPORTS_DIR

_DEFAULT_OUTPUT_DIR = RAG_RETRIEVAL_REPORTS_DIR
_SUMMARY_FILENAME = "retrieval_runs_summary.csv"


def _read_summary(output_dir: Path) -> list[dict]:
    path = output_dir / _SUMMARY_FILENAME
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def _make_embedding_comparison(rows: list[dict], output_dir: Path) -> str | None:
    dense_rows = [r for r in rows if r["retriever"] == "dense"]
    if not dense_rows:
        print("No dense runs found in summary. Skipping embedding comparison.")
        return None

    ranked = sorted(
        dense_rows,
        key=lambda r: (_to_float(r["mrr_at_10"]), _to_float(r["hit_at_5"])),
        reverse=True,
    )
    best = ranked[0]
    best_model = best["model"]

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best_embedding_model": best_model,
        "selection_criterion": "mrr_at_10 (primary), hit_at_5 (tiebreak)",
        "models": [
            {
                "model": r["model"],
                "run_name": r["run_name"],
                "hit_at_5": _to_float(r["hit_at_5"]),
                "recall_at_5": _to_float(r["recall_at_5"]),
                "mrr_at_10": _to_float(r["mrr_at_10"]),
                "latency_seconds": _to_float(r["latency_seconds"]),
                "rank": i + 1,
            }
            for i, r in enumerate(ranked)
        ],
    }

    json_path = output_dir / "embedding_model_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Written: {json_path.name}")

    csv_path = output_dir / "embedding_model_comparison.csv"
    fields = [
        "rank",
        "model",
        "run_name",
        "hit_at_5",
        "recall_at_5",
        "mrr_at_10",
        "latency_seconds",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for m in comparison["models"]:
            writer.writerow({k: m[k] for k in fields})
    print(f"  Written: {csv_path.name}")

    print(
        f"  Best embedding model: {best_model}  mrr@10={_to_float(best['mrr_at_10']):.4f}  hit@5={_to_float(best['hit_at_5']):.4f}"
    )
    return best_model


def _make_hybrid_comparison(rows: list[dict], output_dir: Path) -> dict | None:
    hybrid_rows = [r for r in rows if r["retriever"] == "hybrid"]
    if not hybrid_rows:
        print("No hybrid runs found in summary. Skipping hybrid comparison.")
        return None

    ranked = sorted(
        hybrid_rows,
        key=lambda r: (_to_float(r["mrr_at_10"]), _to_float(r["hit_at_5"])),
        reverse=True,
    )
    best = ranked[0]

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best_alpha": float(best["alpha"]) if best["alpha"] else None,
        "best_model": best["model"],
        "selection_criterion": "mrr_at_10 (primary), hit_at_5 (tiebreak)",
        "runs": [
            {
                "run_name": r["run_name"],
                "model": r["model"],
                "alpha": float(r["alpha"]) if r["alpha"] else None,
                "hit_at_5": _to_float(r["hit_at_5"]),
                "recall_at_5": _to_float(r["recall_at_5"]),
                "mrr_at_10": _to_float(r["mrr_at_10"]),
                "latency_seconds": _to_float(r["latency_seconds"]),
                "rank": i + 1,
            }
            for i, r in enumerate(ranked)
        ],
    }

    json_path = output_dir / "hybrid_alpha_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Written: {json_path.name}")

    csv_path = output_dir / "hybrid_alpha_comparison.csv"
    fields = [
        "rank",
        "run_name",
        "model",
        "alpha",
        "hit_at_5",
        "recall_at_5",
        "mrr_at_10",
        "latency_seconds",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in comparison["runs"]:
            writer.writerow({k: r[k] for k in fields})
    print(f"  Written: {csv_path.name}")

    print(
        f"  Best alpha: {best['alpha']}  mrr@10={_to_float(best['mrr_at_10']):.4f}  hit@5={_to_float(best['hit_at_5']):.4f}"
    )
    return comparison


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate embedding model and hybrid alpha comparison tables.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    return p.parse_args()


def _make_rerank_comparison(rows: list[dict], output_dir: Path) -> dict | None:
    rerank_rows = [r for r in rows if r["retriever"] == "rerank"]
    if not rerank_rows:
        print("No rerank runs found in summary. Skipping rerank comparison.")
        return None

    ranked = sorted(
        rerank_rows,
        key=lambda r: (_to_float(r["mrr_at_10"]), _to_float(r["hit_at_5"])),
        reverse=True,
    )
    best = ranked[0]

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "best_run": best["run_name"],
        "selection_criterion": "mrr_at_10 (primary), hit_at_5 (tiebreak)",
        "runs": [
            {
                "run_name": r["run_name"],
                "model": r["model"],
                "alpha": float(r["alpha"]) if r["alpha"] else None,
                "hit_at_5": _to_float(r["hit_at_5"]),
                "recall_at_5": _to_float(r["recall_at_5"]),
                "mrr_at_10": _to_float(r["mrr_at_10"]),
                "latency_seconds": _to_float(r["latency_seconds"]),
                "rank": i + 1,
            }
            for i, r in enumerate(ranked)
        ],
    }

    json_path = output_dir / "rerank_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Written: {json_path.name}")

    csv_path = output_dir / "rerank_comparison.csv"
    fields = [
        "rank",
        "run_name",
        "model",
        "alpha",
        "hit_at_5",
        "recall_at_5",
        "mrr_at_10",
        "latency_seconds",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in comparison["runs"]:
            writer.writerow({k: r[k] for k in fields})
    print(f"  Written: {csv_path.name}")

    print(
        f"  Best rerank: {best['run_name']}  mrr@10={_to_float(best['mrr_at_10']):.4f}  hit@5={_to_float(best['hit_at_5']):.4f}"
    )
    return comparison


def _make_query_transform_comparison(rows: list[dict], output_dir: Path) -> dict | None:
    qt_rows = [r for r in rows if r["query_transform"] != "none"]
    base_rows = {
        r["retriever"]: r
        for r in rows
        if r["query_transform"] == "none" and r["retriever"] in ("tfidf", "dense")
    }
    if not qt_rows:
        print("No query_transform runs found in summary. Skipping QT comparison.")
        return None

    comparison = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }
    for r in qt_rows:
        base = base_rows.get(r["retriever"])
        entry: dict = {
            "run_name": r["run_name"],
            "retriever": r["retriever"],
            "model": r["model"],
            "query_transform": r["query_transform"],
            "hit_at_5": _to_float(r["hit_at_5"]),
            "recall_at_5": _to_float(r["recall_at_5"]),
            "mrr_at_10": _to_float(r["mrr_at_10"]),
        }
        if base:
            entry["hit_at_5_delta"] = round(
                _to_float(r["hit_at_5"]) - _to_float(base["hit_at_5"]), 4
            )
            entry["mrr_at_10_delta"] = round(
                _to_float(r["mrr_at_10"]) - _to_float(base["mrr_at_10"]), 4
            )
        comparison["runs"].append(entry)

    json_path = output_dir / "query_transform_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Written: {json_path.name}")
    return comparison


def main() -> None:
    args = _parse_args()
    rows = _read_summary(args.output_dir)
    if not rows:
        raise SystemExit(
            f"No summary CSV found at {args.output_dir / _SUMMARY_FILENAME}"
        )

    print(f"Loaded {len(rows)} runs from summary.")
    _make_embedding_comparison(rows, args.output_dir)
    _make_hybrid_comparison(rows, args.output_dir)
    _make_rerank_comparison(rows, args.output_dir)
    _make_query_transform_comparison(rows, args.output_dir)


if __name__ == "__main__":
    main()
