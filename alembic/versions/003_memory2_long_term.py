"""MEMORY-2: long-term episodic memory schema

Revision ID: 003
Revises: 002
Create Date: 2026-05-22

Changes:
- memories.user_id: NOT NULL → nullable (anonymous sessions allowed)
- memories: add conversation_id TEXT nullable
- memories: add memory_type VARCHAR(50) NOT NULL default 'episodic'
- memories: add log_metadata JSONB nullable
- memories: add index on conversation_id

NOTE: pgvector extension is not installed in the current environment.
The embedding column remains ARRAY(Float) as a placeholder.
When pgvector is available: run a separate migration to ALTER the column to
vector(384) (or the chosen dimension) and CREATE INDEX USING ivfflat.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user_id: remove NOT NULL constraint so anonymous chats can write memories
    op.alter_column(
        "memories",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # conversation_id: scope memories to a specific chat session
    op.add_column(
        "memories",
        sa.Column("conversation_id", sa.Text, nullable=True),
    )
    op.create_index("ix_memories_conversation_id", "memories", ["conversation_id"])

    # memory_type: locked to "episodic" for now; extensible later
    op.add_column(
        "memories",
        sa.Column(
            "memory_type",
            sa.String(50),
            nullable=False,
            server_default="episodic",
        ),
    )

    # log_metadata: safe/redacted JSON written by the service layer
    op.add_column(
        "memories",
        sa.Column("log_metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memories", "log_metadata")
    op.drop_column("memories", "memory_type")
    op.drop_index("ix_memories_conversation_id", table_name="memories")
    op.drop_column("memories", "conversation_id")
    op.alter_column(
        "memories",
        "user_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
