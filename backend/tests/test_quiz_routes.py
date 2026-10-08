"""Route ordering: POST /api/quizzes/import must not be shadowed by GET /{quiz_id}."""

from app.routers import quizzes


def _routes():
    return [(r.path, sorted(r.methods or [])) for r in quizzes.router.routes]


def test_import_route_exists():
    routes = _routes()
    assert ("/api/quizzes/import", ["POST"]) in routes


def test_import_defined_before_quiz_id():
    paths = [r.path for r in quizzes.router.routes]
    assert "/api/quizzes/import" in paths
    assert "/api/quizzes/{quiz_id}" in paths
    assert paths.index("/api/quizzes/import") < paths.index("/api/quizzes/{quiz_id}")
