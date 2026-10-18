"""Class setting: require student password to join (off by default)."""

from __future__ import annotations

revision = "0006_class_password"
down_revision = "0005_history_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    try:
        op.add_column("classes", sa.Column("require_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    except Exception:
        pass


def downgrade() -> None:
    from alembic import op

    try:
        op.drop_column("classes", "require_password")
    except Exception:
        pass
