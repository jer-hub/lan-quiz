"""Alembic migration: create active_games snapshot table."""

from __future__ import annotations

revision = "0003_active_games"
down_revision = "0002_assignment_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    try:
        op.create_table(
            "active_games",
            sa.Column("pin", sa.String(10), primary_key=True),
            sa.Column("quiz_id", sa.Integer(), nullable=False),
            sa.Column("quiz_title", sa.String(200), nullable=False),
            sa.Column("teacher_id", sa.Integer(), nullable=True),
            sa.Column("class_id", sa.Integer(), nullable=True),
            sa.Column("assignment_id", sa.Integer(), nullable=True, index=True),
            sa.Column("requires_student_code", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="lobby"),
            sa.Column("current_question_index", sa.Integer(), nullable=False, server_default="-1"),
            sa.Column("questions_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("players_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
    except Exception:
        pass  # table already exists (retry after partial upgrade)


def downgrade() -> None:
    from alembic import op

    try:
        op.drop_table("active_games")
    except Exception:
        pass
