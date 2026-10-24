"""Mastery report CSV export (#17): one row per student, one column per topic."""

import csv
import io

from tests.test_mastery_report import RIGHT, WRONG, Classroom, _question, _teacher, client  # noqa: F401


async def _export(room: Classroom, headers: dict[str, str] | None = None):
    return await room.client.get(f"/api/classes/{room.class_id}/mastery/export", headers=headers or room.teacher)


async def test_the_csv_has_one_row_per_student_and_one_column_per_topic_matching_the_report(client):
    room = await Classroom.create(
        client,
        "t_csv",
        [_question(f"Q{i}", ["Fractions"]) for i in range(1, 6)] + [_question("Q6", ["Decimals"])],
    )
    ada = await room.add_student("Ada", "ada01")
    bea = await room.add_student("Bea", "bea01")
    await room.add_student("Cy", "cy01")  # on the roster, never answered

    await room.submit_attempt(ada, [RIGHT, RIGHT, RIGHT, RIGHT, WRONG, RIGHT])  # Fractions 80%: mastered
    await room.submit_attempt(bea, [RIGHT, RIGHT, WRONG, None, WRONG, RIGHT])  # Fractions 2 of 4: 50%

    res = await _export(room)

    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    assert f'filename="mastery-class-{room.class_id}.csv"' in res.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows == [
        ["student_code", "display_name", "Decimals", "Fractions"],
        ["ADA01", "Ada", "not enough answers", "80% mastered"],
        ["BEA01", "Bea", "not enough answers", "50%"],
        ["CY01", "Cy", "not enough answers", "not enough answers"],
    ]


async def test_a_fractional_accuracy_keeps_one_decimal_place(client):
    room = await Classroom.create(client, "t_csv_frac", [_question(f"Q{i}", ["Fractions"]) for i in range(1, 4)])
    ada = await room.add_student("Ada", "ada01")
    await room.submit_attempt(ada, [RIGHT, RIGHT, WRONG])

    rows = list(csv.reader(io.StringIO((await _export(room)).text)))

    assert rows[1] == ["ADA01", "Ada", "66.7%"]


async def test_another_teacher_cannot_download_the_csv(client):
    room = await Classroom.create(client, "t_csv_owner", [_question("Q1", ["Fractions"])])
    ada = await room.add_student("Ada", "ada01")
    await room.submit_attempt(ada, [RIGHT])
    other = await _teacher(client, "t_csv_other")

    assert (await _export(room, other)).status_code == 404
    assert (await _export(room, ada["headers"])).status_code in (401, 403)
