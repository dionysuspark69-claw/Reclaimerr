"""add_safe_mode_and_preferred_library

- Adds `safe_mode_enabled` (default True) to general_settings so clients can
  gate deletes behind an undo countdown.
- Adds `preferred_library_id` to general_settings so the duplicate scorer can
  prefer a specific library when picking which copy to keep.

Revision ID: 7c2a9e1f4b88
Revises: 3d9f4a7c8b21
Create Date: 2026-04-17 11:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c2a9e1f4b88"
down_revision: Union[str, Sequence[str], None] = "3d9f4a7c8b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("general_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "safe_mode_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "preferred_library_id",
                sa.String(length=50),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("general_settings") as batch_op:
        batch_op.drop_column("preferred_library_id")
        batch_op.drop_column("safe_mode_enabled")
