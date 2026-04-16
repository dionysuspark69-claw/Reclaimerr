"""remove_jellyfin_add_tautulli

Revision ID: 1bc76b93cb52
Revises: 1b25d7fd62d3
Create Date: 2026-04-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1bc76b93cb52"
down_revision: Union[str, None] = "1b25d7fd62d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum values before and after this migration
_OLD_SERVICE_ENUM = ("sonarr", "radarr", "jellyfin", "plex", "seerr")
_NEW_SERVICE_ENUM = ("sonarr", "radarr", "plex", "seerr", "tautulli")


def upgrade() -> None:
    # 1. Delete all Jellyfin rows before touching column types.
    op.execute("DELETE FROM service_configs WHERE service_type = 'jellyfin'")
    op.execute("DELETE FROM movie_versions WHERE service = 'jellyfin'")
    op.execute("DELETE FROM series_service_refs WHERE service = 'jellyfin'")

    # 2. Recreate service_configs.service_type with the new enum (no JELLYFIN, has TAUTULLI).
    with op.batch_alter_table("service_configs", schema=None) as batch_op:
        batch_op.alter_column(
            "service_type",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )

    # 3. Same for movie_versions.service
    with op.batch_alter_table("movie_versions", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )

    # 4. Same for series_service_refs.service
    with op.batch_alter_table("series_service_refs", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
        )

    # 5. Drop jellyfin_season_id from seasons (Plex-only going forward).
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.drop_column("jellyfin_season_id")


def downgrade() -> None:
    # 1. Re-add jellyfin_season_id to seasons.
    with op.batch_alter_table("seasons", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("jellyfin_season_id", sa.String(length=100), nullable=True)
        )

    # 2. Delete any Tautulli rows before reverting enum.
    op.execute("DELETE FROM service_configs WHERE service_type = 'tautulli'")
    op.execute("DELETE FROM movie_versions WHERE service = 'tautulli'")
    op.execute("DELETE FROM series_service_refs WHERE service = 'tautulli'")

    # 3. Restore series_service_refs.service to old enum.
    with op.batch_alter_table("series_service_refs", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )

    # 4. Restore movie_versions.service to old enum.
    with op.batch_alter_table("movie_versions", schema=None) as batch_op:
        batch_op.alter_column(
            "service",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )

    # 5. Restore service_configs.service_type to old enum.
    with op.batch_alter_table("service_configs", schema=None) as batch_op:
        batch_op.alter_column(
            "service_type",
            type_=sa.Enum(*_OLD_SERVICE_ENUM, name="service"),
            existing_type=sa.Enum(*_NEW_SERVICE_ENUM, name="service"),
        )
