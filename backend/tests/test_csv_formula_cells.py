"""CSV exports never hand a spreadsheet a formula: a cell starting with =, +, - or @ is kept as text."""

import csv
import io

from tests.test_mastery_report import RIGHT, Classroom, _question, client  # noqa: F401


async def _rows(room: Classroom, path: str) -> list[list[str]]:
    res = await room.client.get(path, headers=room.teacher)
    assert res.status_code == 200, res.text
    return list(csv.reader(io.StringIO(res.text)))


async def test_a_student_name_starting_with_a_formula_sign_is_text_in_the_mastery_csv(client):
    room = await Classroom.create(client, "t_csv_inject", [_question("Q1", ["Fractions"])])
    student = await room.add_student("=HYPERLINK(\"http://x\")", "ada01")
    await room.submit_attempt(student, [RIGHT])

    rows = await _rows(room, f"/api/classes/{room.class_id}/mastery/export")

    assert rows[1][1] == "'=HYPERLINK(\"http://x\")"


async def test_a_student_name_starting_with_a_formula_sign_is_text_in_the_gradebook_csv(client):
    room = await Classroom.create(client, "t_gb_inject", [_question("Q1", ["Fractions"])])
    await room.add_student("=1+2", "ada01")
    await room.add_student("+Bea", "bea01")
    await room.add_student("-Cy", "cy01")
    await room.add_student("@Di", "di01")

    rows = await _rows(room, f"/api/gradebook/{room.class_id}/export")

    assert sorted(r[1] for r in rows[1:]) == sorted(["'=1+2", "'+Bea", "'-Cy", "'@Di"])
