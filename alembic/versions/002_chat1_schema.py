"""CHAT-1: auth + widget config schema

Revision ID: 002
Revises: 001
Create Date: 2026-05-21

Changes:
- users: add is_active bool (default true)
- widget_configs: replace generic (name, config) with structured columns
- audit_logs: rename user_id->actor_user_id, resource_type->target_type,
              resource_id->target_id, extra->metadata
- conversations: make user_id nullable, add widget_id FK
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: add is_active ---
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # --- widget_configs: drop generic table, recreate with structured schema ---
    op.drop_table("widget_configs")
    op.create_table(
        "widget_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "public_widget_id",
            UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("allowed_origins", JSONB, nullable=False, server_default="[]"),
        sa.Column("theme", JSONB, nullable=False, server_default="{}"),
        sa.Column("greeting", sa.Text, nullable=True),
        sa.Column("enabled_tools", JSONB, nullable=False, server_default="[]"),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "public_widget_id", name="uq_widget_configs_public_widget_id"
        ),
    )
    op.create_index(
        "ix_widget_configs_owner_user_id", "widget_configs", ["owner_user_id"]
    )

    # --- audit_logs: rename columns ---
    op.alter_column("audit_logs", "user_id", new_column_name="actor_user_id")
    op.alter_column("audit_logs", "resource_type", new_column_name="target_type")
    op.alter_column("audit_logs", "resource_id", new_column_name="target_id")
    op.alter_column("audit_logs", "extra", new_column_name="metadata")

    # --- conversations: user_id nullable, add widget_id ---
    op.alter_column(
        "conversations", "user_id", existing_type=UUID(as_uuid=True), nullable=True
    )
    op.add_column(
        "conversations",
        sa.Column(
            "widget_id",
            UUID(as_uuid=True),
            sa.ForeignKey("widget_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_conversations_widget_id", "conversations", ["widget_id"])


def downgrade() -> None:
    # --- conversations: remove widget_id, restore user_id not-null ---
    op.drop_index("ix_conversations_widget_id", table_name="conversations")
    op.drop_column("conversations", "widget_id")
    op.alter_column(
        "conversations", "user_id", existing_type=UUID(as_uuid=True), nullable=False
    )

    # --- audit_logs: restore original column names ---
    op.alter_column("audit_logs", "metadata", new_column_name="extra")
    op.alter_column("audit_logs", "target_id", new_column_name="resource_id")
    op.alter_column("audit_logs", "target_type", new_column_name="resource_type")
    op.alter_column("audit_logs", "actor_user_id", new_column_name="user_id")

    # --- widget_configs: restore generic table ---
    op.drop_index("ix_widget_configs_owner_user_id", table_name="widget_configs")
    op.drop_table("widget_configs")
    op.create_table(
        "widget_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", name="uq_widget_configs_name"),
    )

    # --- users: drop is_active ---
    op.drop_column("users", "is_active")
