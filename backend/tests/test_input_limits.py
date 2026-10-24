"""Input limits over HTTP: image upload size (refused while reading) and teacher CSV row cap."""

import httpx

from app.auth import require_teacher
from app.database import get_db
from app.main import fastapi_app
from app.models import User

ROSTER_HEADER = "username,password,first_name,last_name,email,school_id,class_section"


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class _FakeDB:
    """Stands in for AsyncSession: the import route only needs execute/add/commit."""

    async def execute(self, *_args, **_kwargs):
        return _FakeResult()

    def add(self, _obj):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


async def _fake_db():
    yield _FakeDB()


def _teacher_overrides():
    fastapi_app.dependency_overrides[require_teacher] = lambda: User(
        id=1, username="teacher1", role="teacher"
    )
    fastapi_app.dependency_overrides[get_db] = _fake_db


def _clear_overrides():
    fastapi_app.dependency_overrides.pop(require_teacher, None)
    fastapi_app.dependency_overrides.pop(get_db, None)


def _teacher_csv(data_rows: int) -> bytes:
    lines = [ROSTER_HEADER]
    lines += [f"tch{i:05d},,First{i},Last{i},,S,-" for i in range(data_rows)]
    return ("\n".join(lines) + "\n").encode("utf-8")


async def _post_teacher_csv(data_rows: int) -> httpx.Response:
    _teacher_overrides()
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/auth/teachers/import",
                files={"file": ("teachers.csv", _teacher_csv(data_rows), "text/csv")},
            )
    finally:
        _clear_overrides()


async def test_teacher_csv_500_data_rows_accepted():
    resp = await _post_teacher_csv(500)
    assert resp.status_code == 200, resp.text


async def test_teacher_csv_501_data_rows_refused_with_clear_message():
    resp = await _post_teacher_csv(501)
    assert resp.status_code == 400
    assert "500" in resp.json()["detail"]


async def test_image_upload_refused_before_whole_body_is_read():
    boundary = "LANQUIZBOUNDARY"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="big.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("ascii")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    body_size = 20_000_000  # 20 MB, ten times the limit
    chunk = b"\0" * 65_536
    consumed = 0

    async def body():
        nonlocal consumed
        yield head
        consumed += len(head)
        sent = 0
        while sent < body_size:
            yield chunk
            consumed += len(chunk)
            sent += len(chunk)
        yield tail
        consumed += len(tail)

    _teacher_overrides()
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/quizzes/upload-image",
                content=body(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
    finally:
        _clear_overrides()

    assert resp.status_code == 413
    # The server must stop pulling the body once it passes the 2 MB limit,
    # so it never reads anywhere near the full 20 MB.
    assert consumed < 4_000_000, f"server read {consumed} bytes before refusing"
