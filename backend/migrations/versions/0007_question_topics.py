"""Topics on questions: per-teacher topics and the question-topic link."""

from __future__ import annotations

revision = "0007_question_topics"
down_revision = "0006_class_password"
branch_labels = None
depends_on = None


def _tables(op) -> set[str]:
    import sqlalchemy as sa

    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    # Fresh installs get these tables from the baseline create_all, so only create what is missing.
    existing = _tables(op)
    if "topics" not in existing:
        op.create_table(
            "topics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("key", sa.String(80), nullable=False),
            sa.UniqueConstraint("teacher_id", "key", name="uq_teacher_topic_key"),
        )
        op.create_index("ix_topics_teacher_id", "topics", ["teacher_id"])
    if "question_topics" not in existing:
        op.create_table(
            "question_topics",
            sa.Column(
                "question_id",
                sa.Integer(),
                sa.ForeignKey("questions.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    from alembic import op

    existing = _tables(op)
    if "question_topics" in existing:
        op.drop_table("question_topics")
    if "topics" in existing:
        op.drop_index("ix_topics_teacher_id", table_name="topics")
        op.drop_table("topics")
