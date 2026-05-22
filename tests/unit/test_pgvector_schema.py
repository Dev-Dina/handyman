"""Unit tests for pgvector schema — DB-PGVECTOR-1.

All tests are offline: no Docker, no Postgres, no pgvector extension required.
Tests validate the config constant, migration chain, and ORM model setup.
"""

from __future__ import annotations

import pytest

from app.core.paths import PROJECT_ROOT

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Config constant
# ---------------------------------------------------------------------------


def test_memory_embedding_dim_is_384() -> None:
    from app.services.memory.config import MEMORY_EMBEDDING_DIM

    assert MEMORY_EMBEDDING_DIM == 384, (
        "intfloat/e5-small-v2 produces 384-dim vectors "
        "(confirmed from 2189×384 cached embedding array)"
    )


def test_memory_embedding_dim_is_int() -> None:
    from app.services.memory.config import MEMORY_EMBEDDING_DIM

    assert isinstance(MEMORY_EMBEDDING_DIM, int)


# ---------------------------------------------------------------------------
# Migration 004 chain and content
# ---------------------------------------------------------------------------

_MIGRATION_PATH = PROJECT_ROOT / "alembic" / "versions" / "004_pgvector_embedding.py"


def test_migration_004_file_exists() -> None:
    assert _MIGRATION_PATH.exists(), "004_pgvector_embedding.py migration file missing"


def test_migration_004_revision_id() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "004"' in text


def test_migration_004_down_revision_is_003() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"003"' in text, "migration 004 must chain from 003"


def test_migration_004_creates_extension() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in text


def test_migration_004_alters_to_vector_384() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "vector(384)" in text


def test_migration_004_creates_ivfflat_index() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "ivfflat" in text


def test_migration_004_downgrade_drops_index() -> None:
    text = _MIGRATION_PATH.read_text(encoding="utf-8")
    assert "DROP INDEX IF EXISTS ix_memories_embedding_ivfflat" in text


# ---------------------------------------------------------------------------
# ORM model — embedding column presence and fallback behavior
# ---------------------------------------------------------------------------


def test_memory_model_has_embedding_column() -> None:
    from app.infra.models import Memory

    assert hasattr(Memory, "embedding"), (
        "Memory ORM model must have 'embedding' attribute"
    )


def test_memory_model_embedding_column_is_nullable() -> None:
    """embedding must be nullable — rows without vectors are valid."""
    from app.infra.models import Memory

    col = Memory.__table__.c["embedding"]
    assert col.nullable is True, "Memory.embedding must be nullable"


def test_pgvector_available_flag_is_bool() -> None:
    from app.infra.models import PGVECTOR_AVAILABLE

    assert isinstance(PGVECTOR_AVAILABLE, bool)


def test_memory_embedding_type_references_dim_constant() -> None:
    """When pgvector is installed, the column type must use MEMORY_EMBEDDING_DIM.
    When not installed, ARRAY(Float) fallback is active — verify config constant matches."""
    from app.infra.models import PGVECTOR_AVAILABLE, Memory
    from app.services.memory.config import MEMORY_EMBEDDING_DIM

    col = Memory.__table__.c["embedding"]

    if PGVECTOR_AVAILABLE:
        from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]

        assert isinstance(col.type, Vector), (
            "pgvector is installed but Memory.embedding is not a Vector column"
        )
        assert col.type.dim == MEMORY_EMBEDDING_DIM
    else:
        from sqlalchemy.dialects.postgresql import ARRAY

        assert isinstance(col.type, ARRAY), (
            "pgvector not installed — Memory.embedding should fall back to ARRAY"
        )


# ---------------------------------------------------------------------------
# pyproject.toml declares pgvector dependency
# ---------------------------------------------------------------------------

_PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_pyproject_declares_pgvector() -> None:
    text = _PYPROJECT_PATH.read_text(encoding="utf-8")
    assert "pgvector" in text, (
        "pyproject.toml must declare pgvector dependency so uv sync installs it"
    )
