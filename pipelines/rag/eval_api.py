"""RAG API eval harness — calls retrieve() directly, no HTTP, no torch, CI-safe.

Default mode: TF-IDF only (alpha=0.0). No modelserver, no network required.
Pass --alpha 0.7 for hybrid evaluation (requires modelserver to be live).

Metrics computed:
  hit@5    — 1 if any ground_truth_chunk_id appears in top-5 results
  recall@5 — fraction of ground_truth_chunk_ids found in top-5
  mrr@10   — 1/rank of first ground_truth_chunk_id in top-10 (0 if absent)

Usage:
    python -m pipelines.rag.eval_api
    python -m pipelines.rag.eval_api --alpha 0.7
    python -m pipelines.rag.eval_api --query-transform technical_terms
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.rag.config import (
    RAG_API_EVAL_REPORT_PATH,
    RAG_GOLDEN_PATH,
)
from app.services.rag.query_transform import VALID_TRANSFORMS
from app.services.rag.retrieval import retrieve

_EVAL_TOP_K = 10  # retrieve top-10 so both hit@5 and mrr@10 can be computed
_HIT_K = 5
_MRR_K = 10


def _load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _compute_metrics(
    results: list[dict],
    *,
    top_k_hit: int = _HIT_K,
    top_k_mrr: int = _MRR_K,
) -> dict:
    n = len(results)
    if n == 0:
        return {"hit_at_5": 0.0, "recall_at_5": 0.0, "mrr_at_10": 0.0, "n_questions": 0}

    hit_sum = 0.0
    recall_sum = 0.0
    rr_sum = 0.0

    for item in results:
        gt_ids = set(item["ground_truth_chunk_ids"])
        retrieved_ids = [c["chunk_id"] for c in item["retrieved_chunks"]]

        top_hit = retrieved_ids[:top_k_hit]
        top_mrr = retrieved_ids[:top_k_mrr]

        hit_sum += int(bool(gt_ids & set(top_hit)))
        recall_sum += len(gt_ids & set(top_hit)) / max(len(gt_ids), 1)

        rr = 0.0
        for rank, cid in enumerate(top_mrr, start=1):
            if cid in gt_ids:
                rr = 1.0 / rank
                break
        rr_sum += rr

    return {
        "hit_at_5": round(hit_sum / n, 4),
        "recall_at_5": round(recall_sum / n, 4),
        "mrr_at_10": round(rr_sum / n, 4),
        "n_questions": n,
    }


async def _run_eval(
    golden: list[dict], alpha: float, query_transform: str
) -> list[dict]:
    results: list[dict] = []
    for item in golden:
        question: str = item["question"]
        gt_ids: list[str] = item.get("ground_truth_chunk_ids", [])
        chunks, mode = await retrieve(
            question, top_k=_EVAL_TOP_K, alpha=alpha, query_transform=query_transform
        )
        results.append(
            {
                "golden_id": item.get("golden_id", ""),
                "question": question,
                "ground_truth_chunk_ids": gt_ids,
                "retrieved_chunks": [
                    {"chunk_id": c.get("chunk_id", ""), "score": c.get("score", 0.0)}
                    for c in chunks
                ],
                "retrieval_mode": mode,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG API eval harness (CI-safe, no torch)"
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.0,
        help="Hybrid alpha (0.0 = TF-IDF only, CI default; 0.7 = E5 hybrid)",
    )
    parser.add_argument(
        "--query-transform",
        choices=list(VALID_TRANSFORMS),
        default="none",
        help="Query transform to apply before retrieval",
    )
    args = parser.parse_args()

    if not RAG_GOLDEN_PATH.exists():
        raise FileNotFoundError(f"Golden set not found: {RAG_GOLDEN_PATH}")

    golden = _load_golden(RAG_GOLDEN_PATH)
    results = asyncio.run(
        _run_eval(golden, alpha=args.alpha, query_transform=args.query_transform)
    )
    metrics = _compute_metrics(results)

    retrieval_mode_label = "tfidf" if args.alpha == 0.0 else "hybrid"
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "golden_path": str(RAG_GOLDEN_PATH),
        "n_questions": len(golden),
        "alpha": args.alpha,
        "query_transform": args.query_transform,
        "retrieval_mode": retrieval_mode_label,
        **metrics,
        "per_question": results,
    }

    RAG_API_EVAL_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RAG_API_EVAL_REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(
        f"hit@5={metrics['hit_at_5']:.4f}  "
        f"recall@5={metrics['recall_at_5']:.4f}  "
        f"mrr@10={metrics['mrr_at_10']:.4f}  "
        f"(n={metrics['n_questions']}, mode={retrieval_mode_label}, qt={args.query_transform})"
    )
    print(f"Report: {RAG_API_EVAL_REPORT_PATH}")


if __name__ == "__main__":
    main()
