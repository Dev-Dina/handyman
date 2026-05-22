"""Runtime constants for the memory services (short-term and long-term)."""

from __future__ import annotations

# Short-term (Redis)
MEMORY_TTL_SECONDS: int = 24 * 60 * 60  # 24 hours — one working day of active context
MEMORY_MAX_ITEMS: int = 50
MEMORY_KEY_PREFIX: str = "memory:short_term"

# Long-term (Postgres)
LONG_TERM_MEMORY_TYPE: str = "episodic"
LONG_TERM_AUDIT_ACTION: str = "memory.write"
LONG_TERM_AUDIT_TARGET_TYPE: str = "memory"
LONG_TERM_LIST_LIMIT: int = 50
# intfloat/e5-small-v2 output dimension — confirmed from 2189×384 cached embeddings
MEMORY_EMBEDDING_DIM: int = 384
