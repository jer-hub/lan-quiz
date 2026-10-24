"""Mastery report from homework attempts (#14): each student's accuracy on each topic."""

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
    """A two-option question whose correct answer is option 0."""
    return {
        "text": text,
        "options": ["right", "wrong"],
        "correct_indices": [0],
        "time_limit": 20,
        "kind": "mc",
        "topics": topics or [],
    }


class Classroom:
    """A teacher's class with one quiz assigned as homework, driven through the HTTP API."""

    def __init__(self, client: httpx.AsyncClient, teacher: dict[str, str], class_id: int, join_code: str):
        self.client = client
        self.teacher = teacher
        self.class_id = class_id
        self.join_code = join_code
        self.quiz: dict = {}
        self.assignment_id = 0

    @classmethod
    async def create(cls, client, username: str, questions: list[dict]) -> "Classroom":
        teacher = await _teacher(client, username)
        res = await client.post("/api/classes", json={"name": "Period 1"}, headers=teacher)
        assert res.status_code == 201, res.text
        room = cls(client, teacher, res.json()["id"], res.json()["join_code"])
        res = await client.post("/api/quizzes", json={"title": "Homework", "questions": questions}, headers=teacher)
        assert res.status_code == 201, res.text
        room.quiz = res.json()
        res = await client.post(
            "/api/assignments", json={"class_id": room.class_id, "quiz_id": room.quiz["id"]}, headers=teacher
        )
        assert res.status_code == 201, res.text
        room.assignment_id = res.json()["id"]
        return room

    async def add_student(self, name: str, code: str) -> dict:
        res = await self.client.post(
            f"/api/classes/{self.class_id}/students",
            json={"display_name": name, "student_code": code, "password": "pass1234"},
            headers=self.teacher,
        )
        assert res.status_code == 201, res.text
        login = await self.client.post(
            "/api/auth/student/login",
            json={"student_code": code, "password": "pass1234", "join_code": self.join_code},
        )
        assert login.status_code == 200, login.text
        return {"id": res.json()["id"], "headers": {"Authorization": f"Bearer {login.json()['token']}"}}

    async def submit_attempt(self, student: dict, choices: list[int | None]) -> None:
        """Submit one homework attempt. choices[i] is the option picked for question i (0 is right), None skips it."""
        res = await self.client.post(f"/api/assignments/{self.assignment_id}/attempts", headers=student["headers"])
        assert res.status_code == 201, res.text
        attempt_id = res.json()["id"]
        answers = [
            {"order_index": i, "option_index": choice} for i, choice in enumerate(choices) if choice is not None
        ]
        res = await self.client.post(
            f"/api/attempts/{attempt_id}/submit", json={"answers": answers}, headers=student["headers"]
        )
        assert res.status_code == 200, res.text

    async def report(self, headers: dict[str, str] | None = None) -> httpx.Response:
        return await self.client.get(f"/api/classes/{self.class_id}/mastery", headers=headers or self.teacher)

    async def mastery_report(self) -> dict:
        res = await self.report()
        assert res.status_code == 200, res.text
        return res.json()


def _cell(report: dict, student_id: int, topic: str) -> dict:
    row = next(r for r in report["rows"] if r["student_id"] == student_id)
    return next(c for c in row["cells"] if c["topic"] == topic)


RIGHT, WRONG = 0, 1


async def test_a_submitted_attempt_shows_the_students_accuracy_on_each_topic(client):
    room = await Classroom.create(
        client,
        "t_basic",
        [_question("Q1", ["Fractions"]), _question("Q2", ["Fractions"]), _question("Q3", ["Fractions", "Decimals"]),
         _question("Q4", ["Decimals"]), _question("Q5", ["Decimals"])],
    )
    ada = await room.add_student("Ada", "ada01")

    await room.submit_attempt(ada, [RIGHT, RIGHT, WRONG, RIGHT, RIGHT])

    report = await room.mastery_report()
    assert report["topics"] == ["Decimals", "Fractions"]
    fractions = _cell(report, ada["id"], "Fractions")
    assert fractions["answer_count"] == 3
    assert fractions["accuracy"] == pytest.approx(66.7)
    decimals = _cell(report, ada["id"], "Decimals")
    assert decimals["answer_count"] == 3
    assert decimals["accuracy"] == pytest.approx(66.7)


async def test_accuracy_counts_only_the_most_recent_10_answers_on_a_topic(client):
    room = await Classroom.create(client, "t_window", [_question("Q1", ["Fractions"])])
    ada = await room.add_student("Ada", "ada01")

    # Five early mistakes, then ten correct answers: the early mistakes fall out of the window.
    for _ in range(5):
        await room.submit_attempt(ada, [WRONG])
    for _ in range(10):
        await room.submit_attempt(ada, [RIGHT])

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert fractions["answer_count"] == 10
    assert fractions["accuracy"] == 100


async def test_fewer_than_3_answers_on_a_topic_is_not_enough_answers(client):
    room = await Classroom.create(client, "t_few", [_question("Q1", ["Fractions"]), _question("Q2", ["Fractions"])])
    ada = await room.add_student("Ada", "ada01")
    bea = await room.add_student("Bea", "bea01")

    await room.submit_attempt(ada, [RIGHT, RIGHT])
    await room.submit_attempt(bea, [RIGHT, RIGHT])
    await room.submit_attempt(bea, [RIGHT, None])

    report = await room.mastery_report()
    ada_cell = _cell(report, ada["id"], "Fractions")
    assert ada_cell["answer_count"] == 2
    assert ada_cell["accuracy"] is None
    assert ada_cell["mastered"] is False
    bea_cell = _cell(report, bea["id"], "Fractions")
    assert bea_cell["answer_count"] == 3
    assert bea_cell["accuracy"] == 100


async def test_a_topic_at_or_above_80_percent_is_mastered_and_below_is_not(client):
    room = await Classroom.create(client, "t_mastered", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 6)])
    ada = await room.add_student("Ada", "ada01")
    bea = await room.add_student("Bea", "bea01")

    await room.submit_attempt(ada, [RIGHT, RIGHT, RIGHT, RIGHT, WRONG])  # 80%
    await room.submit_attempt(bea, [RIGHT, RIGHT, RIGHT, WRONG, WRONG])  # 60%

    report = await room.mastery_report()
    assert report["mastery_threshold"] == 80
    ada_cell = _cell(report, ada["id"], "Fractions")
    assert (ada_cell["accuracy"], ada_cell["mastered"]) == (80, True)
    bea_cell = _cell(report, bea["id"], "Fractions")
    assert (bea_cell["accuracy"], bea_cell["mastered"]) == (60, False)


async def test_answers_on_topics_differing_only_in_case_or_spacing_combine_into_one_topic(client):
    import json

    import app.database as database
    from app.mastery import ANSWER_SOURCE_HOMEWORK
    from app.models import AnswerRecord

    room = await Classroom.create(client, "t_merge", [_question("Q1", ["Long division"])])
    ada = await room.add_student("Ada", "ada01")
    # Answers recorded under three spellings of one topic (as stored on each answer when it was given).
    async with database.AsyncSessionLocal() as session:
        for spelling, correct in [("Long division", True), ("long  division", True), (" LONG DIVISION ", False)]:
            session.add(
                AnswerRecord(
                    student_id=ada["id"],
                    class_id=room.class_id,
                    topics_json=json.dumps([spelling]),
                    correct=correct,
                    source=ANSWER_SOURCE_HOMEWORK,
                )
            )
        await session.commit()

    report = await room.mastery_report()
    assert len(report["topics"]) == 1
    assert report["topics"][0].casefold().split() == ["long", "division"]
    cell = _cell(report, ada["id"], report["topics"][0])
    assert (cell["answer_count"], cell["accuracy"]) == (3, pytest.approx(66.7))


async def test_answers_on_questions_without_topics_are_left_out_of_the_table_and_counted(client):
    room = await Classroom.create(
        client, "t_no_topics", [_question("Q1", ["Fractions"]), _question("Q2"), _question("Q3")]
    )
    ada = await room.add_student("Ada", "ada01")
    bea = await room.add_student("Bea", "bea01")

    await room.submit_attempt(ada, [RIGHT, RIGHT, WRONG])
    await room.submit_attempt(bea, [RIGHT, RIGHT, None])

    report = await room.mastery_report()
    assert report["topics"] == ["Fractions"]
    assert report["answers_without_topics"] == 3


async def test_changing_a_questions_topics_after_an_attempt_does_not_change_that_attempts_topics(client):
    room = await Classroom.create(client, "t_new_topics", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ada01")
    await room.submit_attempt(ada, [RIGHT, RIGHT, RIGHT])

    # The teacher changes every question's topics; editing a quiz replaces its questions.
    questions = room.quiz["questions"]
    for q in questions:
        q["topics"] = ["Decimals"]
    res = await client.put(f"/api/quizzes/{room.quiz['id']}", json={"questions": questions}, headers=room.teacher)
    assert res.status_code == 200, res.text

    report = await room.mastery_report()
    assert report["topics"] == ["Fractions"]
    fractions = _cell(report, ada["id"], "Fractions")
    assert (fractions["answer_count"], fractions["accuracy"]) == (3, 100)


async def test_changing_an_answer_key_does_not_change_a_past_attempts_results(client):
    room = await Classroom.create(client, "t_key", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ada01")
    await room.submit_attempt(ada, [RIGHT, RIGHT, RIGHT])

    # The teacher "fixes" the key so option 1 is right: the attempt was graded against the old key.
    questions = room.quiz["questions"]
    for q in questions:
        q["correct_indices"] = [1]
    res = await client.put(f"/api/quizzes/{room.quiz['id']}", json={"questions": questions}, headers=room.teacher)
    assert res.status_code == 200, res.text

    fractions = _cell(await room.mastery_report(), ada["id"], "Fractions")
    assert fractions["accuracy"] == 100


async def test_a_student_no_longer_on_the_roster_does_not_appear(client):
    room = await Classroom.create(client, "t_roster", [_question("Q1", ["Fractions"]), _question("Q2")])
    ada = await room.add_student("Ada", "ada01")
    bea = await room.add_student("Bea", "bea01")
    await room.submit_attempt(ada, [RIGHT, RIGHT])
    await room.submit_attempt(bea, [RIGHT, None])

    res = await client.delete(f"/api/classes/{room.class_id}/students/{ada['id']}", headers=room.teacher)
    assert res.status_code == 204

    report = await room.mastery_report()
    assert [r["student_id"] for r in report["rows"]] == [bea["id"]]
    assert report["answers_without_topics"] == 0


async def test_another_teacher_cannot_read_the_report(client):
    room = await Classroom.create(client, "t_owner", [_question("Q1", ["Fractions"])])
    ada = await room.add_student("Ada", "ada01")
    await room.submit_attempt(ada, [RIGHT])
    other = await _teacher(client, "t_other")

    assert (await room.report(other)).status_code == 404
    assert (await room.report(ada["headers"])).status_code in (401, 403)


def test_existing_install_gains_the_answer_records_table_and_keeps_its_attempts(tmp_path, monkeypatch):
    import sqlite3

    db_path = tmp_path / "migrate.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    # The baseline builds the current models, so drop the new table to get a database as it was before this ticket.
    command.upgrade(_alembic_cfg(), "0007_question_topics")
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE answer_records")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) "
        "VALUES (1, 'teacher1', 'x', 'teacher', '2026-01-01 00:00:00')"
    )
    now = "2026-01-01 00:00:00"
    conn.execute(
        "INSERT INTO classes (id, teacher_id, name, join_code, require_password, created_at) "
        "VALUES (1, 1, 'P1', 'ABC', 0, ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO students (id, class_id, display_name, student_code, password_hash, created_at) "
        "VALUES (1, 1, 'Ada', 'ADA', 'x', ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO quizzes (id, teacher_id, title, description, created_at, updated_at) VALUES (1, 1, 'Old', '', ?, ?)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO assignments (id, class_id, quiz_id, title, status, score_policy, created_at) "
        "VALUES (1, 1, 1, 'HW', 'open', 'best', ?)",
        (now,),
    )
    conn.execute(
        "INSERT INTO attempts (id, assignment_id, student_id, score, answers_json, started_at) "
        "VALUES (1, 1, 1, 0, '[]', ?)",
        (now,),
    )
    conn.commit()
    conn.close()

    command.upgrade(_alembic_cfg(), "head")

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    attempts = conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
    conn.close()
    assert "answer_records" in tables
    assert attempts == 1
