"""Per-class mastery threshold (#16): teachers set it per class, and the mastery report follows it."""

import sqlite3

import pytest

from alembic import command

from tests.test_mastery_report import (  # noqa: F401  (client is a fixture)
    RIGHT,
    WRONG,
    Classroom,
    _alembic_cfg,
    _cell,
    _question,
    _teacher,
    client,
)


async def _set_threshold(room: Classroom, value) -> "object":
    return await room.client.put(
        f"/api/classes/{room.class_id}", json={"mastery_threshold": value}, headers=room.teacher
    )


async def _room_with_ada_at_80_percent(client, username: str) -> tuple[Classroom, dict]:
    room = await Classroom.create(client, username, [_question(f"Q{i}", ["Fractions"]) for i in range(1, 6)])
    ada = await room.add_student("Ada", f"{username}-ada")
    await room.submit_attempt(ada, [RIGHT, RIGHT, RIGHT, RIGHT, WRONG])
    return room, ada


async def test_raising_the_threshold_above_a_students_accuracy_removes_the_mastered_mark(client):
    room, ada = await _room_with_ada_at_80_percent(client, "t_raise")
    assert _cell(await room.mastery_report(), ada["id"], "Fractions")["mastered"] is True

    res = await _set_threshold(room, 85)
    assert res.status_code == 200, res.text

    report = await room.mastery_report()
    assert report["mastery_threshold"] == 85
    cell = _cell(report, ada["id"], "Fractions")
    assert (cell["accuracy"], cell["mastered"]) == (80, False)


async def test_lowering_the_threshold_to_a_students_accuracy_adds_the_mastered_mark(client):
    room = await Classroom.create(client, "t_lower", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 6)])
    bea = await room.add_student("Bea", "t_lower-bea")
    await room.submit_attempt(bea, [RIGHT, RIGHT, RIGHT, WRONG, WRONG])
    assert _cell(await room.mastery_report(), bea["id"], "Fractions")["mastered"] is False

    assert (await _set_threshold(room, 60)).status_code == 200

    cell = _cell(await room.mastery_report(), bea["id"], "Fractions")
    assert (cell["accuracy"], cell["mastered"]) == (60, True)


@pytest.mark.parametrize("value", [0, 101, -5, 80.5, "80", True, None])
async def test_a_threshold_outside_1_to_100_is_refused_and_the_old_one_kept(client, value):
    room, ada = await _room_with_ada_at_80_percent(client, "t_refuse")

    res = await _set_threshold(room, value)

    assert res.status_code == 422, res.text
    report = await room.mastery_report()
    assert report["mastery_threshold"] == 80
    assert _cell(report, ada["id"], "Fractions")["mastered"] is True


@pytest.mark.parametrize("value", [1, 100])
async def test_the_threshold_can_be_set_to_either_end_of_1_to_100(client, value):
    room, _ = await _room_with_ada_at_80_percent(client, f"t_edge_{value}")

    res = await _set_threshold(room, value)

    assert res.status_code == 200, res.text
    assert res.json()["mastery_threshold"] == value
    assert (await room.mastery_report())["mastery_threshold"] == value


def test_existing_classes_default_to_80_after_the_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "migrate.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite:///{db_path}")
    # The schema as it was before this ticket: fresh installs build it from the models, so drop the new column.
    command.upgrade(_alembic_cfg(), "0008_answer_records")
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE classes DROP COLUMN mastery_threshold")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) "
        "VALUES (1, 'teacher1', 'x', 'teacher', '2026-01-01 00:00:00')"
    )
    conn.execute(
        "INSERT INTO classes (id, teacher_id, name, join_code, created_at) "
        "VALUES (1, 1, 'Old class', 'ABCDEF', '2026-01-01 00:00:00')"
    )
    conn.commit()
    conn.close()

    command.upgrade(_alembic_cfg(), "head")

    conn = sqlite3.connect(db_path)
    value = conn.execute("SELECT mastery_threshold FROM classes WHERE id = 1").fetchone()[0]
    conn.close()
    assert value == 80
