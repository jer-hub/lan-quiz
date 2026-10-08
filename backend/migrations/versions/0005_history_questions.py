"""GameHistory.questions_json + ActiveGame.question_history_json."""

from __future__ import annotations

revision = "0005_history_questions"
down_revision = "0004_kinds_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    import sqlalchemy as sa

    try:
        op.add_column("game_history", sa.Column("questions_json", sa.Text(), server_default="[]"))
    except Exception:
        pass
    try:
        op.add_column("active_games", sa.Column("question_history_json", sa.Text(), server_default="[]"))
    except Exception:
        pass


def downgrade() -> None:
    pass
