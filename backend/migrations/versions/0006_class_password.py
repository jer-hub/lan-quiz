"""Class setting: require student password to join (off by default)."""

from __future__ import annotations

revision = "0006_class_password"
down_revision = "0005_history_questions"
branch_labels = None
depends_on = None


def _has_require_password(op) -> bool:
    import sqlalchemy as sa

    columns = sa.inspect(op.get_bind()).get_columns("classes")
    return any(c["name"] == "require_password" for c in columns)


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    # Fresh installs get the column from the baseline create_all, so only add it when missing.
    if _has_require_password(op):
        return
    op.add_column("classes", sa.Column("require_password", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    from alembic import op

    if _has_require_password(op):
        op.drop_column("classes", "require_password")
