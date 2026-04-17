"""add_duplicates_and_tdarr

- Adds Service.TDARR to the service enum on service_configs / movie_versions /
  series_service_refs.
- Creates duplicate_groups and duplicate_candidates tables for the duplicate
  finder feature.

Revision ID: 3d9f4a7c8b21
Revises: 1bc76b93cb52
Create Date: 2026-04-17 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d9f4a7c8b21"
down_revision: Union[str, None] = "1bc76b93cb52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SERVICE_ENUM = ("sonarr", "radarr", "plex", "seerr", "tautulli")
_NEW_SERVICE_ENUM = ("sonarr", "radarr", "plex", "seerr", "tautulli", "tdarr")


def upgrade() -> None:
    # 1. Extend the service enum on every column that uses it.
    with op.batch_alter_table("service_configs", schema=None) as batch_op:
        batch_op.alter_column(
            "service_type",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )
    with op.batch_alter_table("movie_versions", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )
    with op.batch_alter_table("series_service_refs", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )

    # 2. Create duplicate_groups.
    op.create_table(
        "duplicate_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "media_type",
            sa.Enum("MOVIE", "SERIES", name="mediatype"),
            nullable=False,
        ),
        sa.Column("movie_id", sa.Integer(), nullable=True),
        sa.Column("series_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("detection_kind", sa.String(length=20), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("total_size", sa.Integer(), nullable=False),
        sa.Column("reclaimable_size", sa.Integer(), nullable=False),
        sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series_id"], ["series.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("duplicate_groups", schema=None) as batch_op:
        batch_op.create_index(
            "ix_duplicate_groups_movie_id", ["movie_id"], unique=False
        )
        batch_op.create_index(
            "ix_duplicate_groups_series_id", ["series_id"], unique=False
        )

    # 3. Create duplicate_candidates.
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("movie_version_id", sa.Integer(), nullable=True),
        sa.Column("series_service_ref_id", sa.Integer(), nullable=True),
        sa.Column(
            "service",
            sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            nullable=False,
        ),
        sa.Column("library_id", sa.String(length=100), nullable=True),
        sa.Column("library_name", sa.String(length=255), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("container", sa.String(length=20), nullable=True),
        sa.Column("resolution", sa.String(length=20), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("keep", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"], ["duplicate_groups.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["movie_version_id"], ["movie_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["series_service_ref_id"],
            ["series_service_refs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("duplicate_candidates", schema=None) as batch_op:
        batch_op.create_index(
            "ix_duplicate_candidates_group_id", ["group_id"], unique=False
        )
        batch_op.create_index(
            "ix_duplicate_candidates_movie_version_id",
            ["movie_version_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_duplicate_candidates_series_service_ref_id",
            ["series_service_ref_id"],
            unique=False,
        )


def downgrade() -> None:
    # Drop tables first (they reference the tdarr enum value).
    with op.batch_alter_table("duplicate_candidates", schema=None) as batch_op:
        batch_op.drop_index("ix_duplicate_candidates_series_service_ref_id")
        batch_op.drop_index("ix_duplicate_candidates_movie_version_id")
        batch_op.drop_index("ix_duplicate_candidates_group_id")
    op.drop_table("duplicate_candidates")

    with op.batch_alter_table("duplicate_groups", schema=None) as batch_op:
        batch_op.drop_index("ix_duplicate_groups_series_id")
        batch_op.drop_index("ix_duplicate_groups_movie_id")
    op.drop_table("duplicate_groups")

    # Strip Tdarr rows before reverting enum.
    op.execute("DELETE FROM service_configs WHERE service_type = 'tdarr'")
    op.execute("DELETE FROM movie_versions WHERE service = 'tdarr'")
    op.execute("DELETE FROM series_service_refs WHERE service = 'tdarr'")

    with op.batch_alter_table("series_service_refs", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )
    with op.batch_alter_table("movie_versions", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )
    with op.batch_alter_table("service_configs", schema=None) as batch_op:
        batch_op.alter_column(
            "service_type",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )
