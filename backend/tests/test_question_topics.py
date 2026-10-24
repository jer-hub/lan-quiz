"""Topics on questions (#13): teachers give questions topics that carry through edit, import and export."""

from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND = Path(__file__).resolve().parents[1]


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


@pytest.fixture
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    command.upgrade(_alembic_cfg(), "head")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    import app.database as database

    monkeypatch.setattr(database, "AsyncSessionLocal", session_local)

    from app.main import fastapi_app

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def _teacher(client: httpx.AsyncClient, username: str) -> dict[str, str]:
    # Teacher self-registration closes after the first account, so insert the row directly.
    import app.database as database
    from app.auth import hash_password
    from app.models import User

    async with database.AsyncSessionLocal() as session:
        session.add(User(username=username, password_hash=hash_password("secret123"), role="teacher"))
        await session.commit()
    res = await client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _question(text: str, topics: list[str] | None = None) -> dict:
    q = {"text": text, "options": ["A", "B"], "correct_indices": [0], "time_limit": 20, "kind": "mc"}
    if topics is not None:
        q["topics"] = topics
    return q


async def _create_quiz(client, headers, questions: list[dict], title: str = "Quiz") -> dict:
    res = await client.post("/api/quizzes", json={"title": title, "questions": questions}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


async def test_teacher_adds_several_topics_to_a_question_and_sees_them_after_saving(client):
    headers = await _teacher(client, "t_several")
    quiz = await _create_quiz(client, headers, [_question("1/2 + 1/4?", ["Fractions", "Addition"])])

    assert quiz["questions"][0]["topics"] == ["Fractions", "Addition"]
    fetched = (await client.get(f"/api/quizzes/{quiz['id']}", headers=headers)).json()
    assert fetched["questions"][0]["topics"] == ["Fractions", "Addition"]


async def test_topics_differing_only_in_case_or_spacing_are_the_same_topic(client):
    headers = await _teacher(client, "t_merge")
    await _create_quiz(client, headers, [_question("Q1", ["Fractions"])], title="First")
    second = await _create_quiz(
        client, headers, [_question("Q2", [" fractions ", "long   division", "Long Division"])], title="Second"
    )

    assert second["questions"][0]["topics"] == ["Fractions", "long division"]
    res = await client.get("/api/quizzes/topics", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == ["Fractions", "long division"]


async def test_topic_suggestions_list_only_the_teachers_own_topics(client):
    alice = await _teacher(client, "t_alice")
    bob = await _teacher(client, "t_bob")
    await _create_quiz(client, alice, [_question("Q", ["Fractions", "Decimals"])])
    await _create_quiz(client, bob, [_question("Q", ["Photosynthesis"])])

    assert (await client.get("/api/quizzes/topics", headers=alice)).json() == ["Decimals", "Fractions"]
    assert (await client.get("/api/quizzes/topics", headers=bob)).json() == ["Photosynthesis"]


async def test_topic_suggestions_require_a_teacher(client):
    res = await client.get("/api/quizzes/topics")
    assert res.status_code == 401


async def test_editing_a_quiz_keeps_the_topics_sent_for_each_question(client):
    headers = await _teacher(client, "t_edit")
    quiz = await _create_quiz(
        client, headers, [_question("Q1", ["Fractions"]), _question("Q2", ["Decimals", "Rounding"])]
    )

    # The editor sends back each question as it was loaded, with one typo fixed.
    questions = quiz["questions"]
    questions[0]["text"] = "Q1 fixed"
    res = await client.put(f"/api/quizzes/{quiz['id']}", json={"questions": questions}, headers=headers)
    assert res.status_code == 200, res.text

    fetched = (await client.get(f"/api/quizzes/{quiz['id']}", headers=headers)).json()
    assert [q["topics"] for q in fetched["questions"]] == [["Fractions"], ["Decimals", "Rounding"]]


async def test_editing_a_quiz_can_change_a_questions_topics(client):
    headers = await _teacher(client, "t_new_topics")
    quiz = await _create_quiz(client, headers, [_question("Q1", ["Fractions"])])

    questions = quiz["questions"]
    questions[0]["topics"] = ["Decimals"]
    res = await client.put(f"/api/quizzes/{quiz['id']}", json={"questions": questions}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["questions"][0]["topics"] == ["Decimals"]


async def test_quiz_export_includes_topics_and_import_keeps_them(client):
    exporter = await _teacher(client, "t_export")
    importer = await _teacher(client, "t_import")
    quiz = await _create_quiz(client, exporter, [_question("Q1", ["Fractions", "Addition"]), _question("Q2")])

    exported = (await client.get(f"/api/quizzes/{quiz['id']}/export", headers=exporter)).json()
    assert [q["topics"] for q in exported["questions"]] == [["Fractions", "Addition"], []]

    res = await client.post("/api/quizzes/import", json=exported, headers=importer)
    assert res.status_code == 201, res.text
    assert [q["topics"] for q in res.json()["questions"]] == [["Fractions", "Addition"], []]
    # Imported topics become the importer's own suggestions.
    assert (await client.get("/api/quizzes/topics", headers=importer)).json() == ["Addition", "Fractions"]


async def test_a_quiz_file_without_topics_still_imports(client):
    headers = await _teacher(client, "t_old_file")
    old_file = {
        "title": "Old quiz",
        "description": "",
        "questions": [
            {
                "text": "2 + 2?",
                "image": None,
                "options": ["3", "4"],
                "correct_indices": [1],
                "time_limit": 20,
                "kind": "mc",
                "answer_text": None,
            }
        ],
    }
    res = await client.post("/api/quizzes/import", json=old_file, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["questions"][0]["topics"] == []


async def test_too_many_topics_on_a_question_is_rejected(client):
    headers = await _teacher(client, "t_limit")
    res = await client.post(
        "/api/quizzes",
        json={"title": "Q", "questions": [_question("Q", [f"Topic {i}" for i in range(11)])]},
        headers=headers,
    )
    assert res.status_code == 422


def test_existing_install_gains_topic_tables_and_keeps_its_questions(tmp_path, monkeypatch):
    import sqlite3

    db_path = tmp_path / "migrate.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    # The baseline builds the current models, so drop the new tables to get a database as it was before this ticket.
    command.upgrade(_alembic_cfg(), "0006_class_password")
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE question_topics")
    conn.execute("DROP TABLE topics")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) "
        "VALUES (1, 'teacher1', 'x', 'teacher', '2026-01-01 00:00:00')"
    )
    conn.execute(
        "INSERT INTO quizzes (id, teacher_id, title, description, created_at, updated_at) "
        "VALUES (1, 1, 'Old', '', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
    )
    conn.execute(
        "INSERT INTO questions (id, quiz_id, text, options_json, correct_indices_json, time_limit, order_index, kind) "
        "VALUES (1, 1, '2 + 2?', '[\"3\", \"4\"]', '[1]', 20, 0, 'mc')"
    )
    conn.commit()
    conn.close()

    command.upgrade(_alembic_cfg(), "head")

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    questions = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    conn.close()
    assert {"topics", "question_topics"} <= tables
    assert questions == 1
