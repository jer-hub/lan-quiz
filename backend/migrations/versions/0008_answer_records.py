"""Answer records: per-answer evidence (topics and correctness at answer time) for the mastery report."""

from __future__ import annotations

revision = "0008_answer_records"
down_revision = "0007_question_topics"
branch_labels = None
depends_on = None


def _tables(op) -> set[str]:
    import sqlalchemy as sa

    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    # Fresh installs get this table from the baseline create_all, so only create it when missing.
    if "answer_records" in _tables(op):
        return
    op.create_table(
        "answer_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topics_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("attempts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("history_id", sa.Integer(), sa.ForeignKey("game_history.id", ondelete="SET NULL"), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_answer_records_student_id", "answer_records", ["student_id"])
    op.create_index("ix_answer_records_class_id", "answer_records", ["class_id"])


def downgrade() -> None:
    from alembic import op

    if "answer_records" in _tables(op):
        op.drop_index("ix_answer_records_class_id", table_name="answer_records")
        op.drop_index("ix_answer_records_student_id", table_name="answer_records")
        op.drop_table("answer_records")
