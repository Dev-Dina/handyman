"""RAG retrieval service — runtime-safe, no torch/transformers.

Hybrid E5 + TF-IDF (alpha=0.7). Query embedding via model server HTTP boundary.
Chunk corpus and precomputed chunk embeddings loaded lazily from disk.
Falls back to pure TF-IDF when the model server is unavailable or chunk
embeddings have not been pre-generated.

Thin-chunk filter: heading-only or very short chunks are ranked last so they
do not appear as top results when better content is available.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.domain.errors import ModelServerUnavailableError, RagCorpusNotReadyError
from app.infra.tracing import get_tracer
from app.services.rag.config import (
    DEFAULT_TOP_K,
    E5_QUERY_PREFIX,
    HYBRID_ALPHA,
    MODELSERVER_DEFAULT_URL,
    RAG_CHUNK_EMBEDDINGS_PATH,
    RAG_CHUNKS_SECTION_PATH,
    RETRIEVAL_EMBEDDING_MODEL,
    THIN_CHUNK_MIN_BODY_CHARS,
    TFIDF_MAX_FEATURES,
)
from app.services.rag.query_transform import apply as transform_query

# ---------------------------------------------------------------------------
# Module-level corpus cache — populated on first request
# ---------------------------------------------------------------------------
_chunks: list[dict] | None = None
_tfidf_vec: TfidfVectorizer | None = None
_tfidf_mat = None  # scipy sparse (N, vocab)
_chunk_vecs: np.ndarray | None = None  # (N, D) float32, L2-normalized

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")


def _load_chunks() -> list[dict]:
    global _chunks
    if _chunks is not None:
        return _chunks
    path: Path = RAG_CHUNKS_SECTION_PATH
    if not path.exists():
        raise RagCorpusNotReadyError(f"Chunk corpus missing: {path}")
    rows: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    _chunks = rows
    return _chunks


def _get_tfidf(chunks: list[dict]):
    global _tfidf_vec, _tfidf_mat
    if _tfidf_vec is not None:
        return _tfidf_vec, _tfidf_mat
    texts = [c.get("text", "") for c in chunks]
    vec = TfidfVectorizer(max_features=TFIDF_MAX_FEATURES, sublinear_tf=True)
    mat = vec.fit_transform(texts)
    _tfidf_vec = vec
    _tfidf_mat = mat
    return _tfidf_vec, _tfidf_mat


def _load_chunk_vecs() -> np.ndarray | None:
    global _chunk_vecs
    if _chunk_vecs is not None:
        return _chunk_vecs
    if not RAG_CHUNK_EMBEDDINGS_PATH.exists():
        return None
    _chunk_vecs = np.load(str(RAG_CHUNK_EMBEDDINGS_PATH)).astype(np.float32)
    return _chunk_vecs


def _minmax(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    return (arr - lo) / max(hi - lo, 1e-9)


def _filter_indices(
    chunks: list[dict],
    source_type: str | None,
    maintainer_only: bool,
) -> list[int]:
    indices = [
        i
        for i, c in enumerate(chunks)
        if (source_type is None or c.get("source_type") == source_type)
        and (not maintainer_only or str(c.get("is_maintainer_like", "False")) == "True")
    ]
    return indices if indices else list(range(len(chunks)))


def _is_thin_chunk(text: str) -> bool:
    """Return True for heading-only or very-short-with-no-body chunks."""
    stripped = text.strip()
    if len(stripped) >= THIN_CHUNK_MIN_BODY_CHARS:
        return False
    return bool(_HEADING_RE.match(stripped))


def _apply_thin_filter(chunks: list[dict]) -> list[dict]:
    """Reorder so thin chunks come after substantive ones; never drops chunks."""
    substantive = [c for c in chunks if not _is_thin_chunk(c.get("text", ""))]
    thin = [c for c in chunks if _is_thin_chunk(c.get("text", ""))]
    return substantive + thin


async def retrieve(
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    source_type: str | None = None,
    maintainer_only: bool = False,
    query_transform: str = "none",
    modelserver_url: str = MODELSERVER_DEFAULT_URL,
    embedding_model: str = RETRIEVAL_EMBEDDING_MODEL,
    alpha: float = HYBRID_ALPHA,
) -> tuple[list[dict], str]:
    """Return (ranked_chunks, mode) where mode is 'hybrid', 'tfidf', or 'tfidf_fallback'.

    Each returned chunk dict has a 'score' key added.
    Heading-only / thin chunks are pushed past substantive results when possible.
    Raises RagCorpusNotReadyError if the chunk file is missing.
    """
    tracer = get_tracer()

    with tracer.start_span("rag.retrieve") as span:
        span.set_attribute("top_k", str(top_k))
        span.set_attribute("alpha", str(alpha))
        span.set_attribute("query_transform", query_transform)
        if source_type:
            span.set_attribute("source_type", source_type)
        span.set_attribute("maintainer_only", str(maintainer_only))

        # Apply query transform
        with tracer.start_span("rag.query_transform"):
            query = transform_query(question, query_transform)

        chunks = _load_chunks()

        with tracer.start_span("rag.metadata_filter") as mf_span:
            mask = _filter_indices(chunks, source_type, maintainer_only)
            mf_span.set_attribute("chunk_count", str(len(chunks)))
            mf_span.set_attribute("filtered_count", str(len(mask)))
        filtered = [chunks[i] for i in mask]

        tfidf_vec, tfidf_mat_full = _get_tfidf(chunks)
        tfidf_sub = tfidf_mat_full[mask]

        q_tfidf = tfidf_vec.transform([query])
        tfidf_scores = np.asarray(sk_cosine(q_tfidf, tfidf_sub)).flatten()

        mode = "tfidf" if alpha == 0.0 else "tfidf_fallback"
        combined = tfidf_scores.copy()

        chunk_vecs = _load_chunk_vecs()
        if chunk_vecs is not None and alpha > 0.0:
            from app.infra.modelserver_client import ModelServerClient

            client = ModelServerClient(base_url=modelserver_url)
            try:
                with tracer.start_span("rag.modelserver_embedding") as emb_span:
                    emb_span.set_attribute("model", embedding_model)
                    prefixed = E5_QUERY_PREFIX + query
                    embeddings = await client.embed([prefixed], model=embedding_model)
                q_vec = np.array(embeddings[0], dtype=np.float32)
                norm = float(np.linalg.norm(q_vec))
                if norm > 0:
                    q_vec /= norm
                sub_vecs = chunk_vecs[mask]  # (N_filtered, D)
                dense_scores = (sub_vecs @ q_vec).flatten()
                combined = alpha * _minmax(dense_scores) + (1.0 - alpha) * _minmax(
                    tfidf_scores
                )
                mode = "hybrid"
            except ModelServerUnavailableError:
                with tracer.start_span("rag.tfidf_fallback"):
                    pass  # combined already holds tfidf_scores

        top_indices = np.argsort(combined)[::-1][:top_k]
        ranked: list[dict] = []
        for idx in top_indices:
            chunk = dict(filtered[int(idx)])
            chunk["score"] = float(combined[int(idx)])
            ranked.append(chunk)

        results = _apply_thin_filter(ranked)

        span.set_attribute("returned_count", str(len(results)))
        span.set_attribute("retriever_used", mode)

    return results, mode
