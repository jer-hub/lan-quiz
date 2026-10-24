"""Class setting: mastery threshold, the percent accuracy at which a topic counts as mastered (default 80)."""

from __future__ import annotations

revision = "0009_class_mastery_threshold"
down_revision = "0008_answer_records"
branch_labels = None
depends_on = None


def _has_mastery_threshold(op) -> bool:
    import sqlalchemy as sa

    columns = sa.inspect(op.get_bind()).get_columns("classes")
    return any(c["name"] == "mastery_threshold" for c in columns)


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    # Fresh installs get the column from the baseline create_all, so only add it when missing.
    if _has_mastery_threshold(op):
        return
    op.add_column("classes", sa.Column("mastery_threshold", sa.Integer(), nullable=False, server_default="80"))


def downgrade() -> None:
    from alembic import op

    if _has_mastery_threshold(op):
        op.drop_column("classes", "mastery_threshold")
