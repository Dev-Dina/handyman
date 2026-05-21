"""Retrieval evaluation harness for the Advanced RAG pipeline.

Supports TF-IDF lexical baseline, dense embedding (AutoModel mean-pooling),
hybrid sparse+dense, and optional cross-encoder reranking.

Also supports deterministic query transformation (technical_terms) and
corpus metadata filtering (source_type, issue_number, maintainer_only).

Usage examples:
    python -m pipelines.rag.eval_retrieval --retriever tfidf
    python -m pipelines.rag.eval_retrieval --retriever tfidf --query-transform technical_terms
    python -m pipelines.rag.eval_retrieval --retriever dense --model BAAI/bge-small-en-v1.5
    python -m pipelines.rag.eval_retrieval --retriever hybrid --model BAAI/bge-small-en-v1.5 --alpha 0.5
    python -m pipelines.rag.eval_retrieval --retriever rerank --model BAAI/bge-small-en-v1.5 --alpha 0.5 --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
    python -m pipelines.rag.eval_retrieval --retriever tfidf --filter-source-type docs
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.rag.config import (
    RAG_CHUNKS_SECTION_PATH,
    RAG_EMBEDDINGS_CACHE_DIR,
    RAG_GOLDEN_PATH,
    RAG_RETRIEVAL_REPORTS_DIR,
)
from app.services.rag.query_transform import apply as _apply_query_transform

if TYPE_CHECKING:
    import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TOP_K = 10
_DEFAULT_OUTPUT_DIR = RAG_RETRIEVAL_REPORTS_DIR
_EMBEDDINGS_CACHE_DIR = RAG_EMBEDDINGS_CACHE_DIR
_SUMMARY_FILENAME = "retrieval_runs_summary.csv"

_SAFE_RE = re.compile(r"[^a-zA-Z0-9]")

# Model-specific query/passage prefixes for retrieval tasks
_QUERY_PREFIXES: dict[str, str] = {
    "intfloat/e5-small-v2": "query: ",
    "intfloat/e5-base-v2": "query: ",
    "intfloat/e5-large-v2": "query: ",
}
_PASSAGE_PREFIXES: dict[str, str] = {
    "intfloat/e5-small-v2": "passage: ",
    "intfloat/e5-base-v2": "passage: ",
    "intfloat/e5-large-v2": "passage: ",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _load_golden() -> list[dict]:
    records: list[dict] = []
    with open(RAG_GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _load_chunks() -> list[dict]:
    chunks: list[dict] = []
    with open(RAG_CHUNKS_SECTION_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def _apply_filters(
    chunks: list[dict],
    source_type: str | None,
    issue_number: str | None,
    maintainer_only: bool,
) -> list[dict]:
    out = chunks
    if source_type:
        out = [c for c in out if c.get("source_type") == source_type]
    if issue_number:
        out = [c for c in out if str(c.get("issue_number", "")) == issue_number]
    if maintainer_only:
        out = [c for c in out if str(c.get("is_maintainer_like", "")).lower() == "true"]
    return out


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def _safe_name(s: str) -> str:
    return _SAFE_RE.sub("_", s)


def _build_run_name(
    retriever: str,
    model: str | None,
    alpha: float | None,
    query_transform: str,
    rerank_model: str | None,
    filter_source_type: str | None,
    filter_maintainer_only: bool,
) -> str:
    if retriever == "tfidf":
        name = "tfidf_section_aware"
    elif retriever == "dense":
        name = f"dense_{_safe_name(model or '')}"
    elif retriever == "hybrid":
        alpha_str = f"{alpha}".replace(".", "_")
        name = f"hybrid_{_safe_name(model or '')}_alpha{alpha_str}"
    else:  # rerank
        alpha_str = f"{alpha}".replace(".", "_")
        name = (
            f"rerank_{_safe_name(model or '')}_alpha{alpha_str}"
            f"_{_safe_name(rerank_model or '')}"
        )
    if query_transform != "none":
        name += f"_qt_{query_transform}"
    if filter_source_type:
        name += f"_fst_{filter_source_type}"
    if filter_maintainer_only:
        name += "_maintainer"
    return name


# ---------------------------------------------------------------------------
# Query transformation
# ---------------------------------------------------------------------------


def _transform_query(question: str, mode: str) -> str:
    return _apply_query_transform(question, mode)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _metrics(gt_ids: list[str], ranked_ids: list[str]) -> dict[str, float]:
    gt_set = set(gt_ids)
    top5 = set(ranked_ids[:5])
    hit5 = float(bool(gt_set & top5))
    recall5 = len(gt_set & top5) / max(len(gt_set), 1)
    rr = 0.0
    for rank, cid in enumerate(ranked_ids[:10], start=1):
        if cid in gt_set:
            rr = 1.0 / rank
            break
    return {"hit_at_5": hit5, "recall_at_5": recall5, "reciprocal_rank": rr}


def _aggregate(per_q: list[dict]) -> dict[str, float]:
    n = len(per_q)
    if n == 0:
        return {"hit_at_5": 0.0, "recall_at_5": 0.0, "mrr_at_10": 0.0}
    return {
        "hit_at_5": sum(r["hit_at_5"] for r in per_q) / n,
        "recall_at_5": sum(r["recall_at_5"] for r in per_q) / n,
        "mrr_at_10": sum(r["reciprocal_rank"] for r in per_q) / n,
    }


# ---------------------------------------------------------------------------
# Dense embedding — _Embedder loads model once and reuses it
# ---------------------------------------------------------------------------


class _Embedder:
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        from transformers import AutoModel, AutoTokenizer

        self._model_name = model_name
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._model.eval()
        self._model.to(device)
        self._device = device

    def embed(self, texts: list[str], batch_size: int = 64) -> "np.ndarray":
        import numpy as np
        import torch

        all_vecs: list = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = self._tok(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            enc = {k: v.to(self._device) for k, v in enc.items()}
            with torch.no_grad():
                out = self._model(**enc)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = pooled.cpu().float().numpy()
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.maximum(norms, 1e-9)
            all_vecs.append(pooled)
        return np.vstack(all_vecs)


def _get_or_build_chunk_vecs(
    chunks: list[dict],
    embedder: "_Embedder",
    model_name: str,
    p_prefix: str,
    cache_dir: Path,
) -> "np.ndarray":
    import numpy as np

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{_safe_name(model_name)}_chunks.npy"
    if cache_path.exists():
        print(f"  Loading cached chunk embeddings: {cache_path.name}")
        return np.load(str(cache_path))
    texts = [p_prefix + c["text"] for c in chunks]
    print(f"  Embedding {len(texts)} chunks with {model_name} ...")
    vecs = embedder.embed(texts)
    np.save(str(cache_path), vecs)
    print(f"  Cached to {cache_path.name}")
    return vecs


# ---------------------------------------------------------------------------
# Score normalization for hybrid combination
# ---------------------------------------------------------------------------


def _minmax_norm(arr: "np.ndarray") -> "np.ndarray":
    import numpy as np

    lo, hi = arr.min(), arr.max()
    return (arr - lo) / np.maximum(hi - lo, 1e-9)


# ---------------------------------------------------------------------------
# TF-IDF retrieval
# ---------------------------------------------------------------------------


def _run_tfidf(
    golden: list[dict],
    chunks: list[dict],
    top_k: int,
    query_transform: str,
) -> tuple[list[dict], dict[str, float], float]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

    corpus_texts = [c["text"] for c in chunks]
    chunk_ids = [c["chunk_id"] for c in chunks]
    queries = [_transform_query(item["question"], query_transform) for item in golden]

    t0 = time.monotonic()
    vectorizer = TfidfVectorizer(max_features=50_000, sublinear_tf=True)
    corpus_matrix = vectorizer.fit_transform(corpus_texts)
    q_matrix = vectorizer.transform(queries)
    scores_matrix = sk_cosine(q_matrix, corpus_matrix)
    elapsed = time.monotonic() - t0

    per_q: list[dict] = []
    for i, item in enumerate(golden):
        scores = scores_matrix[i]
        ranked_indices = scores.argsort()[::-1][:top_k]
        ranked_ids = [chunk_ids[j] for j in ranked_indices]
        ranked_scores = [float(scores[j]) for j in ranked_indices]
        m = _metrics(item["ground_truth_chunk_ids"], ranked_ids)
        per_q.append(
            {
                "golden_id": item["golden_id"],
                "question": item["question"],
                "ground_truth_chunk_ids": item["ground_truth_chunk_ids"],
                "retrieved_chunk_ids_top_10": ranked_ids[:10],
                "retrieved_scores_top_10": ranked_scores[:10],
                **m,
            }
        )
    return per_q, _aggregate(per_q), elapsed


# ---------------------------------------------------------------------------
# Dense retrieval
# ---------------------------------------------------------------------------


def _run_dense(
    golden: list[dict],
    chunks: list[dict],
    model_name: str,
    top_k: int,
    query_transform: str,
    device: str,
    cache_dir: Path,
) -> tuple[list[dict], dict[str, float], float]:
    p_prefix = _PASSAGE_PREFIXES.get(model_name, "")
    q_prefix = _QUERY_PREFIXES.get(model_name, "")
    chunk_ids = [c["chunk_id"] for c in chunks]

    t0 = time.monotonic()
    embedder = _Embedder(model_name, device)
    chunk_vecs = _get_or_build_chunk_vecs(
        chunks, embedder, model_name, p_prefix, cache_dir
    )

    questions = [
        q_prefix + _transform_query(item["question"], query_transform)
        for item in golden
    ]
    print(f"  Embedding {len(questions)} questions ...")
    q_vecs = embedder.embed(questions)
    elapsed = time.monotonic() - t0

    scores_matrix = q_vecs @ chunk_vecs.T  # (N_q, N_c)
    per_q: list[dict] = []
    for i, item in enumerate(golden):
        scores = scores_matrix[i]
        ranked_indices = scores.argsort()[::-1][:top_k]
        ranked_ids = [chunk_ids[j] for j in ranked_indices]
        ranked_scores = [float(scores[j]) for j in ranked_indices]
        m = _metrics(item["ground_truth_chunk_ids"], ranked_ids)
        per_q.append(
            {
                "golden_id": item["golden_id"],
                "question": item["question"],
                "ground_truth_chunk_ids": item["ground_truth_chunk_ids"],
                "retrieved_chunk_ids_top_10": ranked_ids[:10],
                "retrieved_scores_top_10": ranked_scores[:10],
                **m,
            }
        )
    return per_q, _aggregate(per_q), elapsed


# ---------------------------------------------------------------------------
# Hybrid sparse+dense retrieval
# ---------------------------------------------------------------------------


def _run_hybrid(
    golden: list[dict],
    chunks: list[dict],
    model_name: str,
    alpha: float,
    top_k: int,
    query_transform: str,
    device: str,
    cache_dir: Path,
) -> tuple[list[dict], dict[str, float], float]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

    p_prefix = _PASSAGE_PREFIXES.get(model_name, "")
    q_prefix = _QUERY_PREFIXES.get(model_name, "")
    chunk_ids = [c["chunk_id"] for c in chunks]
    corpus_texts = [c["text"] for c in chunks]
    queries = [_transform_query(item["question"], query_transform) for item in golden]

    t0 = time.monotonic()

    # Sparse scores
    vectorizer = TfidfVectorizer(max_features=50_000, sublinear_tf=True)
    corpus_mat = vectorizer.fit_transform(corpus_texts)
    q_sparse = vectorizer.transform(queries)
    tfidf_matrix = sk_cosine(q_sparse, corpus_mat).astype(np.float32)  # (N_q, N_c)

    # Dense scores
    embedder = _Embedder(model_name, device)
    chunk_vecs = _get_or_build_chunk_vecs(
        chunks, embedder, model_name, p_prefix, cache_dir
    )
    print(f"  Embedding {len(queries)} questions ...")
    q_vecs = embedder.embed([q_prefix + q for q in queries])
    dense_matrix = (q_vecs @ chunk_vecs.T).astype(np.float32)  # (N_q, N_c)

    elapsed = time.monotonic() - t0

    per_q: list[dict] = []
    for i, item in enumerate(golden):
        tfidf_norm = _minmax_norm(tfidf_matrix[i])
        dense_norm = _minmax_norm(dense_matrix[i])
        hybrid_scores = alpha * dense_norm + (1.0 - alpha) * tfidf_norm
        ranked_indices = hybrid_scores.argsort()[::-1][:top_k]
        ranked_ids = [chunk_ids[j] for j in ranked_indices]
        ranked_scores = [float(hybrid_scores[j]) for j in ranked_indices]
        m = _metrics(item["ground_truth_chunk_ids"], ranked_ids)
        per_q.append(
            {
                "golden_id": item["golden_id"],
                "question": item["question"],
                "ground_truth_chunk_ids": item["ground_truth_chunk_ids"],
                "retrieved_chunk_ids_top_10": ranked_ids[:10],
                "retrieved_scores_top_10": ranked_scores[:10],
                **m,
            }
        )
    return per_q, _aggregate(per_q), elapsed


# ---------------------------------------------------------------------------
# Cross-encoder reranker
# ---------------------------------------------------------------------------


def _run_rerank(
    golden: list[dict],
    chunks: list[dict],
    dense_model: str,
    rerank_model: str,
    alpha: float,
    top_k: int,
    query_transform: str,
    device: str,
    cache_dir: Path,
    retrieval_pool: int = 20,
) -> tuple[list[dict], dict[str, float], float]:
    """Hybrid retrieval (top retrieval_pool) followed by cross-encoder reranking."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    # First: hybrid retrieval with larger pool
    per_q_hybrid, _, t_hybrid = _run_hybrid(
        golden,
        chunks,
        dense_model,
        alpha,
        retrieval_pool,
        query_transform,
        device,
        cache_dir,
    )

    # Build chunk lookup
    chunk_by_id = {c["chunk_id"]: c["text"] for c in chunks}

    t0 = time.monotonic()
    print(f"  Loading reranker: {rerank_model} ...")
    re_tok = AutoTokenizer.from_pretrained(rerank_model)
    re_model = AutoModelForSequenceClassification.from_pretrained(rerank_model)
    re_model.eval()
    re_model.to(device)

    per_q: list[dict] = []
    for i, item in enumerate(golden):
        candidates = per_q_hybrid[i]["retrieved_chunk_ids_top_10"][:retrieval_pool]
        candidate_texts = [chunk_by_id.get(cid, "") for cid in candidates]
        question = _transform_query(item["question"], query_transform)
        pairs = [[question, txt] for txt in candidate_texts]
        enc = re_tok(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = re_model(**enc).logits.squeeze(-1)
        rerank_scores = logits.cpu().float().numpy()
        ranked_indices = rerank_scores.argsort()[::-1][:top_k]
        ranked_ids = [candidates[j] for j in ranked_indices]
        ranked_scores = [float(rerank_scores[j]) for j in ranked_indices]
        m = _metrics(item["ground_truth_chunk_ids"], ranked_ids)
        per_q.append(
            {
                "golden_id": item["golden_id"],
                "question": item["question"],
                "ground_truth_chunk_ids": item["ground_truth_chunk_ids"],
                "retrieved_chunk_ids_top_10": ranked_ids[:10],
                "retrieved_scores_top_10": ranked_scores[:10],
                **m,
            }
        )

    elapsed = t_hybrid + (time.monotonic() - t0)
    return per_q, _aggregate(per_q), elapsed


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def _write_outputs(
    run_name: str,
    retriever: str,
    model: str | None,
    alpha: float | None,
    query_transform: str,
    chunks_evaluated: int,
    per_q: list[dict],
    agg: dict[str, float],
    elapsed: float,
    output_dir: Path,
    extra_meta: dict | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    summary: dict = {
        "run_name": run_name,
        "retriever": retriever,
        "model": model,
        "alpha": alpha,
        "query_transform": query_transform,
        "chunk_count": chunks_evaluated,
        "question_count": len(per_q),
        "hit_at_5": round(agg["hit_at_5"], 4),
        "recall_at_5": round(agg["recall_at_5"], 4),
        "mrr_at_10": round(agg["mrr_at_10"], 4),
        "latency_seconds": round(elapsed, 2),
        "timestamp": timestamp,
        **(extra_meta or {}),
        "per_question": per_q,
    }

    json_path = output_dir / f"{run_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"  Written: {json_path.name}")

    csv_fields = [
        "golden_id",
        "question",
        "ground_truth_chunk_ids",
        "retrieved_chunk_ids_top_10",
        "hit_at_5",
        "recall_at_5",
        "reciprocal_rank",
    ]
    csv_path = output_dir / f"{run_name}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for row in per_q:
            row2 = dict(row)
            row2["ground_truth_chunk_ids"] = ";".join(row2["ground_truth_chunk_ids"])
            row2["retrieved_chunk_ids_top_10"] = ";".join(
                row2["retrieved_chunk_ids_top_10"]
            )
            writer.writerow(row2)
    print(f"  Written: {csv_path.name}")

    _append_summary(
        run_name,
        retriever,
        model,
        alpha,
        query_transform,
        chunks_evaluated,
        agg,
        elapsed,
        timestamp,
        output_dir,
    )


def _append_summary(
    run_name: str,
    retriever: str,
    model: str | None,
    alpha: float | None,
    query_transform: str,
    chunk_count: int,
    agg: dict[str, float],
    elapsed: float,
    timestamp: str,
    output_dir: Path,
) -> None:
    summary_path = output_dir / _SUMMARY_FILENAME
    fields = [
        "run_name",
        "retriever",
        "model",
        "alpha",
        "query_transform",
        "chunk_count",
        "hit_at_5",
        "recall_at_5",
        "mrr_at_10",
        "latency_seconds",
        "timestamp",
    ]
    write_header = not summary_path.exists()
    with open(summary_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "run_name": run_name,
                "retriever": retriever,
                "model": model or "",
                "alpha": alpha if alpha is not None else "",
                "query_transform": query_transform,
                "chunk_count": chunk_count,
                "hit_at_5": round(agg["hit_at_5"], 4),
                "recall_at_5": round(agg["recall_at_5"], 4),
                "mrr_at_10": round(agg["mrr_at_10"], 4),
                "latency_seconds": round(elapsed, 2),
                "timestamp": timestamp,
            }
        )
    print(f"  Appended to: {summary_path.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Retrieval eval harness: TF-IDF, dense (AutoModel mean-pool), "
            "hybrid sparse+dense, optional rerank."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--retriever",
        choices=["tfidf", "dense", "hybrid", "rerank"],
        required=True,
        help="Retrieval strategy to evaluate.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="HuggingFace model ID for dense/hybrid/rerank (required for those modes).",
    )
    p.add_argument(
        "--alpha",
        type=float,
        default=0.5,
        help="Dense weight for hybrid/rerank in [0, 1].",
    )
    p.add_argument(
        "--rerank-model",
        default=None,
        help="Cross-encoder model for --retriever rerank.",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=_DEFAULT_TOP_K,
        help="Number of candidates to retrieve.",
    )
    p.add_argument(
        "--query-transform",
        choices=["none", "technical_terms"],
        default="none",
        help="Deterministic query transformation mode.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory for JSON/CSV output.",
    )
    p.add_argument(
        "--device",
        default="cuda",
        help="PyTorch device for dense models (cuda or cpu).",
    )
    # Metadata filters
    p.add_argument(
        "--filter-source-type",
        default=None,
        choices=["docs", "issue", "comment"],
        help="Restrict corpus to this source type.",
    )
    p.add_argument(
        "--filter-issue-number",
        default=None,
        help="Restrict corpus to a specific issue number.",
    )
    p.add_argument(
        "--filter-maintainer-only",
        action="store_true",
        help="Restrict corpus to is_maintainer_like=True chunks.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    if args.retriever in ("dense", "hybrid", "rerank") and not args.model:
        raise SystemExit("--model is required for --retriever dense, hybrid, or rerank")
    if args.retriever == "rerank" and not args.rerank_model:
        raise SystemExit("--rerank-model is required for --retriever rerank")

    golden = _load_golden()
    chunks = _load_chunks()
    chunks = _apply_filters(
        chunks,
        args.filter_source_type,
        args.filter_issue_number,
        args.filter_maintainer_only,
    )
    print(f"Golden examples: {len(golden)}, Corpus chunks: {len(chunks)}")

    run_name = _build_run_name(
        args.retriever,
        args.model,
        args.alpha,
        args.query_transform,
        args.rerank_model,
        args.filter_source_type,
        args.filter_maintainer_only,
    )
    print(f"Run: {run_name}")

    if args.retriever == "tfidf":
        per_q, agg, elapsed = _run_tfidf(
            golden, chunks, args.top_k, args.query_transform
        )
    elif args.retriever == "dense":
        per_q, agg, elapsed = _run_dense(
            golden,
            chunks,
            args.model,
            args.top_k,
            args.query_transform,
            args.device,
            _EMBEDDINGS_CACHE_DIR,
        )
    elif args.retriever == "hybrid":
        per_q, agg, elapsed = _run_hybrid(
            golden,
            chunks,
            args.model,
            args.alpha,
            args.top_k,
            args.query_transform,
            args.device,
            _EMBEDDINGS_CACHE_DIR,
        )
    else:  # rerank
        per_q, agg, elapsed = _run_rerank(
            golden,
            chunks,
            args.model,
            args.rerank_model,
            args.alpha,
            args.top_k,
            args.query_transform,
            args.device,
            _EMBEDDINGS_CACHE_DIR,
        )

    print(
        f"Results: hit@5={agg['hit_at_5']:.4f}  "
        f"recall@5={agg['recall_at_5']:.4f}  "
        f"mrr@10={agg['mrr_at_10']:.4f}  "
        f"time={elapsed:.1f}s"
    )

    _write_outputs(
        run_name,
        args.retriever,
        args.model,
        args.alpha,
        args.query_transform,
        len(chunks),
        per_q,
        agg,
        elapsed,
        args.output_dir,
    )


if __name__ == "__main__":
    main()
