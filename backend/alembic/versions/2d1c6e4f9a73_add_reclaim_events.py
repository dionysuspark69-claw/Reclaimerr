"""add_reclaim_events

Adds `reclaim_events` table — an append-only audit log of every reclaimed
file, indexed by created_at + source for Reports tab queries.

Revision ID: 2d1c6e4f9a73
Revises: 7c2a9e1f4b88
Create Date: 2026-04-17 13:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2d1c6e4f9a73"
down_revision: Union[str, Sequence[str], None] = "7c2a9e1f4b88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reclaim_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source",
            sa.Enum(
                "rule_based",
                "duplicate",
                "tdarr",
                "manual",
                name="reclaimsource",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "media_type",
            sa.Enum("movie", "series", name="mediatype", native_enum=False),
            nullable=False,
        ),
        sa.Column("media_title", sa.String(length=512), nullable=False),
        sa.Column("media_year", sa.SmallInteger(), nullable=True),
        sa.Column("bytes_reclaimed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "triggered_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_reclaim_events_source", "reclaim_events", ["source"]
    )
    op.create_index(
        "ix_reclaim_events_created_at", "reclaim_events", ["created_at"]
    )
    op.create_index(
        "ix_reclaim_events_triggered_by_user_id",
        "reclaim_events",
        ["triggered_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reclaim_events_triggered_by_user_id", table_name="reclaim_events")
    op.drop_index("ix_reclaim_events_created_at", table_name="reclaim_events")
    op.drop_index("ix_reclaim_events_source", table_name="reclaim_events")
    op.drop_table("reclaim_events")
