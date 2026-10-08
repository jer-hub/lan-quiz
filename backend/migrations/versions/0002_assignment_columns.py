"""Ensure assignments.max_attempts/score_policy (replaces manual ALTER)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_assignment_columns"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent for DBs created before Alembic (manual ALTER era).
    # add_column fails if the column already exists -> swallow.
    try:
        op.add_column("assignments", sa.Column("max_attempts", sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column(
            "assignments",
            sa.Column("score_policy", sa.String(20), nullable=False, server_default="best"),
        )
    except Exception:
        pass


def downgrade() -> None:
    pass
