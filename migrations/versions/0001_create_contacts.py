"""create contacts table

Revision ID: 0001
Revises:
Create Date: 2026-07-22

Первая миграция: таблица contacts. Enum-поля хранятся как VARCHAR
(native_enum=False) — переносимо между Postgres и SQLite и не требует
ALTER TYPE при добавлении новых значений категорий.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="other"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("suggested_reply", sa.Text(), nullable=True),
        sa.Column("ai_provider", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="received"),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_contacts_email", "contacts", ["email"])
    op.create_index("ix_contacts_status", "contacts", ["status"])
    op.create_index("ix_contacts_created_at", "contacts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contacts_created_at", table_name="contacts")
    op.drop_index("ix_contacts_status", table_name="contacts")
    op.drop_index("ix_contacts_email", table_name="contacts")
    op.drop_table("contacts")
