"""Google AI Studio (Gemini) is the only AI quiz provider.

Seam: the HTTP endpoints through an ASGI client. The provider call (httpx.AsyncClient)
is faked and records what would have been sent, so no real network traffic happens.
"""

import json
import logging

import httpx
import pytest
from httpx import ASGITransport
from httpx import AsyncClient as RealAsyncClient

from app.auth import require_teacher
from app.main import fastapi_app
from app.models import User

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
TEST_KEY = "AIza-test-key-123"

QUIZ_JSON = json.dumps(
    {
        "title": "Plants",
        "description": "",
        "questions": [
            {"text": f"Question {i}?", "options": ["A", "B", "C"], "correct_indices": [1], "time_limit": 20}
            for i in range(3)
        ],
    }
)


def _ok(url: str) -> httpx.Response:
    body = {"choices": [{"message": {"content": QUIZ_JSON}}]}
    return httpx.Response(200, json=body, request=httpx.Request("POST", url))


class RecordingProvider:
    """Stands in for httpx.AsyncClient; records requests and returns a set reply."""

    sent: list[dict] = []
    client_kwargs: list[dict] = []
    # callable(url) -> httpx.Response, an exception to raise, or a list of those used one per call
    reply = None

    def __init__(self, *args, **kwargs):
        RecordingProvider.client_kwargs.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None, extensions=None):
        RecordingProvider.sent.append({"url": url, "headers": headers or {}, "body": json or {}})
        reply = RecordingProvider.reply
        if isinstance(reply, list):
            reply = reply.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply(url)


@pytest.fixture
def recorder(monkeypatch):
    RecordingProvider.sent = []
    RecordingProvider.client_kwargs = []
    RecordingProvider.reply = _ok
    monkeypatch.setattr(httpx, "AsyncClient", RecordingProvider)
    fastapi_app.dependency_overrides[require_teacher] = lambda: User(id=1)
    yield RecordingProvider
    fastapi_app.dependency_overrides.pop(require_teacher, None)


def _payload(**extra) -> dict:
    return {"model": GEMINI_DEFAULT_MODEL, "api_key": TEST_KEY, "topic": "Photosynthesis", **extra}


async def _post(payload: dict) -> httpx.Response:
    async with RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        return await client.post("/api/ai/generate-quiz", json=payload)


async def test_presets_offer_only_google(recorder):
    async with RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        resp = await client.get("/api/ai/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert [p["id"] for p in data["providers"]] == ["google"]
    assert data["default_provider"] == "google"
    assert data["default_model"] == GEMINI_DEFAULT_MODEL
    assert data["providers"][0]["base_url"] == GEMINI_BASE


async def test_request_goes_to_gemini_with_bearer_key(recorder):
    resp = await _post(_payload(provider="google"))
    assert resp.status_code == 200, resp.text
    sent = recorder.sent[0]
    assert sent["url"] == f"{GEMINI_BASE}/chat/completions"
    assert sent["headers"]["Authorization"] == f"Bearer {TEST_KEY}"
    assert sent["body"]["model"] == GEMINI_DEFAULT_MODEL


async def test_request_leaves_room_for_thinking_and_skips_json_mode(recorder):
    await _post(_payload())
    body = recorder.sent[0]["body"]
    assert body["reasoning_effort"] == "low"
    assert body["max_tokens"] >= 8192
    assert "response_format" not in body


async def test_request_without_provider_uses_google(recorder):
    resp = await _post({"api_key": TEST_KEY, "topic": "Photosynthesis"})
    assert resp.status_code == 200, resp.text
    assert recorder.sent[0]["url"] == f"{GEMINI_BASE}/chat/completions"
    assert recorder.sent[0]["body"]["model"] == GEMINI_DEFAULT_MODEL


@pytest.mark.parametrize("provider", ["groq", "openai", "openrouter", "custom"])
async def test_other_providers_are_refused(recorder, provider):
    resp = await _post(_payload(provider=provider))
    assert resp.status_code == 400
    assert recorder.sent == []


async def test_base_url_in_request_cannot_redirect_the_call(recorder):
    resp = await _post(_payload(base_url="https://elsewhere.example/v1"))
    assert resp.status_code == 200, resp.text
    assert recorder.sent[0]["url"] == f"{GEMINI_BASE}/chat/completions"


async def test_each_attempt_is_limited_to_45_seconds(recorder):
    await _post(_payload())
    timeout = recorder.client_kwargs[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.read == 45
    assert timeout.connect <= 15


async def test_timeout_is_logged_with_elapsed_time(recorder, caplog):
    recorder.reply = httpx.ReadTimeout("slow")
    with caplog.at_level(logging.WARNING, logger="app.routers.ai"):
        await _post(_payload())
    assert any("timed out" in r.getMessage() and "after=" in r.getMessage() for r in caplog.records)


FALLBACK_MODEL = "gemini-3.5-flash-lite"


def _busy(url):
    body = [{"error": {"code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE"}}]
    return httpx.Response(503, json=body, request=httpx.Request("POST", url))


async def test_first_attempt_success_reports_the_chosen_model(recorder):
    resp = await _post(_payload())
    assert resp.status_code == 200
    assert len(recorder.sent) == 1
    assert resp.json()["model_used"] == GEMINI_DEFAULT_MODEL
    assert resp.json()["fallback_used"] is False


@pytest.mark.parametrize("first_failure", [_busy, httpx.ReadTimeout("slow")], ids=["busy", "timeout"])
async def test_busy_or_slow_model_falls_back_once_to_flash_lite(recorder, first_failure):
    recorder.reply = [first_failure, _ok]
    resp = await _post(_payload())
    assert resp.status_code == 200, resp.text
    assert [s["body"]["model"] for s in recorder.sent] == [GEMINI_DEFAULT_MODEL, FALLBACK_MODEL]
    assert resp.json()["model_used"] == FALLBACK_MODEL
    assert resp.json()["fallback_used"] is True


@pytest.mark.parametrize(
    "failures",
    [[_busy, _busy], [httpx.ReadTimeout("slow"), _busy], [_busy, httpx.ReadTimeout("slow")]],
    ids=["busy-busy", "timeout-busy", "busy-timeout"],
)
async def test_both_attempts_busy_or_slow_gives_a_clear_busy_message(recorder, failures):
    recorder.reply = failures
    resp = await _post(_payload())
    assert resp.status_code == 503
    assert "busy" in resp.json()["detail"].lower()
    assert len(recorder.sent) == 2


async def test_flash_lite_is_not_retried_with_itself(recorder):
    recorder.reply = [_busy, _ok]
    resp = await _post(_payload(model=FALLBACK_MODEL))
    assert resp.status_code == 503
    assert len(recorder.sent) == 1


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429])
async def test_other_errors_are_not_retried(recorder, code):
    recorder.reply = [lambda url: httpx.Response(code, json={}, request=httpx.Request("POST", url)), _ok]
    await _post(_payload())
    assert len(recorder.sent) == 1


async def test_provider_reason_logged_without_key_and_not_shown_to_teacher(recorder, caplog):
    def rejected(url):
        body = {"error": {"message": f"API key not valid: {TEST_KEY}", "status": "INVALID_ARGUMENT"}}
        return httpx.Response(400, json=body, request=httpx.Request("POST", url))

    recorder.reply = rejected
    with caplog.at_level(logging.WARNING, logger="app.routers.ai"):
        resp = await _post(_payload())
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "API key not valid" not in detail
    assert TEST_KEY not in detail
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "API key not valid" in logged
    assert TEST_KEY not in logged


@pytest.mark.parametrize("code", [401, 403])
async def test_rejected_key_gets_a_key_hint(recorder, code):
    recorder.reply = lambda url: httpx.Response(code, json={}, request=httpx.Request("POST", url))
    resp = await _post(_payload())
    assert resp.status_code == 502
    assert "API key" in resp.json()["detail"]
