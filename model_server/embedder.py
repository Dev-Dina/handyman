"""E5 text embedder for model_server /embed.

Replicates the EXACT offline encode used to build the cached chunk embeddings
(`pipelines/rag/eval_retrieval._Embedder`): transformers ``AutoModel`` with
attention-masked mean pooling over the last hidden state, then L2 normalization.
This must match the chunk-side embeddings or hybrid scoring is meaningless.

Torch + transformers live only in the model_server image, never in the API image.
The model is loaded lazily and cached for the process lifetime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import EMBED_MAX_LENGTH, EMBED_MODEL_NAME, EMBED_MODEL_PATH

if TYPE_CHECKING:
    import numpy as np

_embedder: "_E5Embedder | None" = None


class EmbedderUnavailableError(RuntimeError):
    """Raised when the embedding model cannot be loaded or used."""


class _E5Embedder:
    def __init__(self, model_ref: str) -> None:
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - import guard
            raise EmbedderUnavailableError(
                "transformers/torch not installed in this image"
            ) from exc
        try:
            self._tok = AutoTokenizer.from_pretrained(model_ref)
            self._model = AutoModel.from_pretrained(model_ref)
            self._model.eval()
        except Exception as exc:
            raise EmbedderUnavailableError(
                f"embedding model failed to load from {model_ref!r}"
            ) from exc

    def embed(self, texts: list[str], batch_size: int = 32) -> "np.ndarray":
        import numpy as np
        import torch

        all_vecs: list = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = self._tok(
                batch,
                padding=True,
                truncation=True,
                max_length=EMBED_MAX_LENGTH,
                return_tensors="pt",
            )
            with torch.no_grad():
                out = self._model(**enc)
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (out.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = pooled.cpu().float().numpy()
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.maximum(norms, 1e-9)
            all_vecs.append(pooled)
        return np.vstack(all_vecs)


def _resolve_model_ref() -> str:
    """Prefer the shipped local model dir; fall back to the hub id."""
    import os

    if os.path.isdir(EMBED_MODEL_PATH):
        return EMBED_MODEL_PATH
    return EMBED_MODEL_NAME


def get_embedder() -> "_E5Embedder":
    global _embedder
    if _embedder is None:
        _embedder = _E5Embedder(_resolve_model_ref())
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts and return plain Python float lists (JSON-serialisable)."""
    vecs = get_embedder().embed(texts)
    return [[float(x) for x in row] for row in vecs]
