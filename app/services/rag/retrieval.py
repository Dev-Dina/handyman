"""RAG retrieval service — runtime-safe, no torch/transformers.

Hybrid E5 + TF-IDF (alpha=0.7). Query embedding via model server HTTP boundary.
Chunk corpus and precomputed chunk embeddings loaded lazily from disk.
Falls back to pure TF-IDF when the model server is unavailable or chunk
embeddings have not been pre-generated.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.domain.errors import ModelServerUnavailableError, RagCorpusNotReadyError
from app.services.rag.config import (
    DEFAULT_TOP_K,
    E5_QUERY_PREFIX,
    HYBRID_ALPHA,
    MODELSERVER_DEFAULT_URL,
    RAG_CHUNK_EMBEDDINGS_PATH,
    RAG_CHUNKS_SECTION_PATH,
    RETRIEVAL_EMBEDDING_MODEL,
    TFIDF_MAX_FEATURES,
)

# ---------------------------------------------------------------------------
# Module-level corpus cache — populated on first request
# ---------------------------------------------------------------------------
_chunks: list[dict] | None = None
_tfidf_vec: TfidfVectorizer | None = None
_tfidf_mat = None  # scipy sparse (N, vocab)
_chunk_vecs: np.ndarray | None = None  # (N, D) float32, L2-normalized


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


async def retrieve(
    question: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    source_type: str | None = None,
    maintainer_only: bool = False,
    modelserver_url: str = MODELSERVER_DEFAULT_URL,
    embedding_model: str = RETRIEVAL_EMBEDDING_MODEL,
    alpha: float = HYBRID_ALPHA,
) -> tuple[list[dict], str]:
    """Return (ranked_chunks, mode) where mode is 'hybrid' or 'tfidf_fallback'.

    Each returned chunk dict has a 'score' key added.
    Raises RagCorpusNotReadyError if the chunk file is missing.
    """
    chunks = _load_chunks()
    mask = _filter_indices(chunks, source_type, maintainer_only)
    filtered = [chunks[i] for i in mask]

    tfidf_vec, tfidf_mat_full = _get_tfidf(chunks)
    tfidf_sub = tfidf_mat_full[mask]

    q_tfidf = tfidf_vec.transform([question])
    tfidf_scores = np.asarray(sk_cosine(q_tfidf, tfidf_sub)).flatten()

    mode = "tfidf_fallback"
    combined = tfidf_scores.copy()

    chunk_vecs = _load_chunk_vecs()
    if chunk_vecs is not None and alpha > 0.0:
        from app.infra.modelserver_client import ModelServerClient

        client = ModelServerClient(base_url=modelserver_url)
        try:
            prefixed = E5_QUERY_PREFIX + question
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
            pass  # keep tfidf_fallback

    top_indices = np.argsort(combined)[::-1][:top_k]
    results: list[dict] = []
    for idx in top_indices:
        chunk = dict(filtered[int(idx)])
        chunk["score"] = float(combined[int(idx)])
        results.append(chunk)
    return results, mode
