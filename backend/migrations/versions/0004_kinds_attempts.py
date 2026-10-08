"""Question kinds + attempts table."""

from __future__ import annotations

revision = "0004_kinds_attempts"
down_revision = "0003_active_games"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    for col, type_, kwargs in [
        ("kind", sa.String(20), {"server_default": "mc"}),
        ("answer_text", sa.Text(), {}),
    ]:
        try:
            op.add_column("questions", sa.Column(col, type_, **kwargs))
        except Exception:
            pass
    try:
        op.create_table(
            "attempts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("answers_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        )
    except Exception:
        pass


def downgrade() -> None:
    from alembic import op

    try:
        op.drop_table("attempts")
    except Exception:
        pass
    for col in ("answer_text", "kind"):
        try:
            op.drop_column("questions", col)
        except Exception:
            pass
