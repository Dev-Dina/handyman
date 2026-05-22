"""DB-PGVECTOR-1: enable pgvector and migrate Memory.embedding to vector(384)

Revision ID: 004
Revises: 003
Create Date: 2026-05-22

Changes:
- CREATE EXTENSION IF NOT EXISTS vector  (requires pgvector/pgvector:pg16 image)
- ALTER memories.embedding TYPE vector(384)  (dimension = intfloat/e5-small-v2 output)
- CREATE INDEX ix_memories_embedding_ivfflat USING ivfflat(vector_cosine_ops, lists=100)

Note: The vector extension is provided by the pgvector/pgvector:pg16 Docker image
already configured in docker-compose.yml. This migration will fail on vanilla
Postgres images without the pgvector extension installed.

Dimension 384 is the confirmed output size of intfloat/e5-small-v2 (verified
from the 2189×384 cached embedding array in reports/rag/embeddings_cache/).
The constant MEMORY_EMBEDDING_DIM=384 lives in app/services/memory/config.py.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension — idempotent; safe to run multiple times.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Alter embedding column to native vector type.
    # USING NULL::vector(384) safely converts any existing NULL rows.
    op.execute(
        "ALTER TABLE memories "
        "ALTER COLUMN embedding TYPE vector(384) "
        "USING NULL::vector(384)"
    )

    # IVFFlat index for approximate nearest-neighbor cosine search.
    # lists=100 is a safe default for datasets under 1M rows.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding_ivfflat "
        "ON memories USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_ivfflat")

    # Revert to ARRAY(Float) placeholder.
    op.execute(
        "ALTER TABLE memories ALTER COLUMN embedding TYPE float[] USING NULL::float[]"
    )
    # Note: vector extension is intentionally NOT dropped — it may be used by
    # other tables (e.g. chunks when RAG embedding is wired).
