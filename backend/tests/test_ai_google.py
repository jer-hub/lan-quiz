"""Google AI Studio (Gemini) quiz generation through the Interactions API.

Seam: the HTTP endpoints through an ASGI client. The provider call (httpx.AsyncClient)
is faked and records what would have been sent, so no real network traffic happens.
"""

import base64
import json
import logging

import httpx
import pytest
from httpx import ASGITransport
from httpx import AsyncClient as RealAsyncClient

from app.auth import require_teacher
from app.main import fastapi_app
from app.models import User
from app.routers import ai as ai_router

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
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


def _interaction(text: str = QUIZ_JSON, status: str = "completed", extra_steps: list | None = None) -> dict:
    steps = list(extra_steps or [])
    if text is not None:
        steps.append({"type": "model_output", "content": [{"type": "text", "text": text}]})
    return {"id": "interaction-1", "status": status, "steps": steps}


def _ok(url: str) -> httpx.Response:
    return httpx.Response(200, json=_interaction(), request=httpx.Request("POST", url))


def _busy(url):
    body = {"error": {"code": 503, "message": "This model is currently experiencing high demand.", "status": "UNAVAILABLE"}}
    return httpx.Response(503, json=body, request=httpx.Request("POST", url))


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


def _attachment(name: str, mime: str, raw: bytes = b"%PDF-1.4 tiny test file") -> dict:
    return {"name": name, "mime_type": mime, "data": base64.b64encode(raw).decode()}


async def _post(payload: dict, path: str = "/api/ai/generate-quiz") -> httpx.Response:
    async with RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        return await client.post(path, json=payload)


def _items(sent: dict, kind: str) -> list[dict]:
    return [i for i in sent["body"]["input"] if i.get("type") == kind]


# --- Presets and request shape -------------------------------------------------------


async def test_presets_offer_only_google_and_native_attachments(recorder):
    async with RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        resp = await client.get("/api/ai/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert [p["id"] for p in data["providers"]] == ["google"]
    assert data["default_model"] == GEMINI_DEFAULT_MODEL
    assert "extract" not in data
    assert "application/pdf" in data["attachments"]["mime_types"]
    assert data["attachments"]["max_bytes"] > 0


async def test_request_goes_to_interactions_api_with_key_header(recorder):
    resp = await _post(_payload())
    assert resp.status_code == 200, resp.text
    sent = recorder.sent[0]
    assert sent["url"] == INTERACTIONS_URL
    assert sent["headers"]["x-goog-api-key"] == TEST_KEY
    assert "Authorization" not in sent["headers"]
    assert sent["body"]["model"] == GEMINI_DEFAULT_MODEL


async def test_request_is_not_stored_and_keeps_thinking_low(recorder):
    await _post(_payload())
    body = recorder.sent[0]["body"]
    assert body["store"] is False
    assert body["generation_config"]["thinking_level"] == "low"
    assert body["generation_config"]["max_output_tokens"] >= 8192
    assert "JSON" in body["system_instruction"]
    texts = _items(recorder.sent[0], "text")
    assert len(texts) == 1 and "Photosynthesis" in texts[0]["text"]


async def test_request_without_provider_uses_google(recorder):
    resp = await _post({"api_key": TEST_KEY, "topic": "Photosynthesis"})
    assert resp.status_code == 200, resp.text
    assert recorder.sent[0]["body"]["model"] == GEMINI_DEFAULT_MODEL


@pytest.mark.parametrize("provider", ["groq", "openai", "openrouter", "custom"])
async def test_other_providers_are_refused(recorder, provider):
    resp = await _post(_payload(provider=provider))
    assert resp.status_code == 400
    assert recorder.sent == []


async def test_base_url_in_request_cannot_redirect_the_call(recorder):
    resp = await _post(_payload(base_url="https://elsewhere.example/v1"))
    assert resp.status_code == 200, resp.text
    assert recorder.sent[0]["url"] == INTERACTIONS_URL


# --- Attachments: sent to Gemini as-is, no local conversion ---------------------------


async def test_pdf_is_attached_as_a_document(recorder):
    pdf = _attachment("lesson.pdf", "application/pdf")
    resp = await _post(_payload(attachment=pdf))
    assert resp.status_code == 200, resp.text
    docs = _items(recorder.sent[0], "document")
    assert docs == [{"type": "document", "mime_type": "application/pdf", "data": pdf["data"]}]
    assert "attached" in _items(recorder.sent[0], "text")[0]["text"].lower()


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/webp"])
async def test_image_is_attached_as_an_image(recorder, mime):
    img = _attachment("page.png", mime, b"\x89PNG fake")
    resp = await _post(_payload(attachment=img))
    assert resp.status_code == 200, resp.text
    assert _items(recorder.sent[0], "image") == [{"type": "image", "mime_type": mime, "data": img["data"]}]


async def test_attachment_alone_is_enough_without_topic(recorder):
    resp = await _post({"api_key": TEST_KEY, "attachment": _attachment("lesson.pdf", "application/pdf")})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize(
    "mime",
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "application/zip"],
)
async def test_unsupported_attachment_type_is_refused_before_sending(recorder, mime):
    resp = await _post(_payload(attachment=_attachment("lesson.docx", mime)))
    assert resp.status_code == 400
    assert recorder.sent == []


async def test_invalid_base64_attachment_is_refused(recorder):
    bad = {"name": "lesson.pdf", "mime_type": "application/pdf", "data": "not base64!!"}
    resp = await _post(_payload(attachment=bad))
    assert resp.status_code == 400
    assert recorder.sent == []


async def test_oversized_attachment_is_refused_before_sending(recorder, monkeypatch):
    monkeypatch.setattr(ai_router, "MAX_ATTACHMENT_BYTES", 10)
    resp = await _post(_payload(attachment=_attachment("big.pdf", "application/pdf", b"x" * 11)))
    assert resp.status_code == 413
    assert recorder.sent == []


async def test_text_extraction_endpoint_is_gone(recorder):
    async with RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        resp = await client.post("/api/ai/extract-text", files={"file": ("a.txt", b"hello", "text/plain")})
    assert resp.status_code in (404, 405)


# --- Reading the answer ----------------------------------------------------------------


async def test_only_the_model_output_step_is_read(recorder):
    thought = {"type": "thought", "content": [{"type": "text", "text": "thinking, not JSON"}]}
    recorder.reply = lambda url: httpx.Response(
        200, json=_interaction(extra_steps=[thought]), request=httpx.Request("POST", url)
    )
    resp = await _post(_payload())
    assert resp.status_code == 200, resp.text
    assert resp.json()["quiz"]["title"] == "Plants"


async def test_interaction_without_output_is_reported(recorder):
    recorder.reply = lambda url: httpx.Response(
        200, json=_interaction(text=None, status="incomplete"), request=httpx.Request("POST", url)
    )
    resp = await _post(_payload())
    assert resp.status_code == 502
    assert "incomplete" in resp.json()["detail"]


# --- Time limits, errors and fallback -----------------------------------------------


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


async def test_field_violations_from_google_are_logged(recorder, caplog):
    def bad_field(url):
        body = {
            "error": {
                "code": 400,
                "message": "Request contains an invalid argument.",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.BadRequest",
                        "fieldViolations": [{"field": "generation_config.thinking_level", "description": "Unknown value"}],
                    }
                ],
            }
        }
        return httpx.Response(400, json=body, request=httpx.Request("POST", url))

    recorder.reply = bad_field
    with caplog.at_level(logging.WARNING, logger="app.routers.ai"):
        await _post(_payload())
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "generation_config.thinking_level" in logged
    assert "Unknown value" in logged


@pytest.mark.parametrize("code", [401, 403])
async def test_rejected_key_gets_a_key_hint(recorder, code):
    recorder.reply = lambda url: httpx.Response(code, json={}, request=httpx.Request("POST", url))
    resp = await _post(_payload())
    assert resp.status_code == 502
    assert "API key" in resp.json()["detail"]


async def test_first_attempt_success_reports_the_chosen_model(recorder):
    resp = await _post(_payload())
    assert resp.status_code == 200
    assert len(recorder.sent) == 1
    assert resp.json()["model_used"] == GEMINI_DEFAULT_MODEL
    assert resp.json()["fallback_used"] is False


@pytest.mark.parametrize("first_failure", [_busy, httpx.ReadTimeout("slow")], ids=["busy", "timeout"])
async def test_busy_or_slow_model_falls_back_once_to_flash_lite(recorder, first_failure):
    recorder.reply = [first_failure, _ok]
    resp = await _post(_payload(attachment=_attachment("lesson.pdf", "application/pdf")))
    assert resp.status_code == 200, resp.text
    assert [s["body"]["model"] for s in recorder.sent] == [GEMINI_DEFAULT_MODEL, FALLBACK_MODEL]
    # The fallback carries the same attachment.
    assert _items(recorder.sent[1], "document")
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
