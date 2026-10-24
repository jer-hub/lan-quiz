"""Google AI Studio (Gemini) as an AI quiz provider, and the default one.

Seam: the HTTP endpoints through an ASGI client. The provider call (httpx.AsyncClient)
is faked and records what would have been sent, so no real network traffic happens.
"""

import json

import httpx
import pytest
from httpx import ASGITransport
from httpx import AsyncClient as RealAsyncClient

from app.auth import require_teacher
from app.main import fastapi_app
from app.models import User

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"

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


class RecordingProvider:
    """Stands in for httpx.AsyncClient and records each outgoing request."""

    sent: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None, extensions=None):
        RecordingProvider.sent.append({"url": url, "headers": headers or {}, "body": json or {}})
        body = {"choices": [{"message": {"content": QUIZ_JSON}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))


@pytest.fixture
def recorder(monkeypatch):
    RecordingProvider.sent = []
    monkeypatch.setattr(httpx, "AsyncClient", RecordingProvider)
    fastapi_app.dependency_overrides[require_teacher] = lambda: User(id=1)
    yield RecordingProvider
    fastapi_app.dependency_overrides.pop(require_teacher, None)


async def _client():
    return RealAsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")


async def test_presets_offer_google_as_the_default(recorder):
    async with await _client() as client:
        resp = await client.get("/api/ai/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_provider"] == "google"
    assert data["default_model"] == GEMINI_DEFAULT_MODEL
    google = next(p for p in data["providers"] if p["id"] == "google")
    assert google["base_url"] == GEMINI_BASE
    assert google["default_model"] == GEMINI_DEFAULT_MODEL
    assert GEMINI_DEFAULT_MODEL in [m["id"] for m in google["models"]]
    assert data["providers"][0]["id"] == "google"


async def test_google_request_goes_to_gemini_with_bearer_key(recorder):
    payload = {"provider": "google", "model": GEMINI_DEFAULT_MODEL, "api_key": "AIza-test-key-123", "topic": "Photosynthesis"}
    async with await _client() as client:
        resp = await client.post("/api/ai/generate-quiz", json=payload)
    assert resp.status_code == 200, resp.text
    assert len(recorder.sent) == 1
    sent = recorder.sent[0]
    assert sent["url"] == f"{GEMINI_BASE}/chat/completions"
    assert sent["headers"]["Authorization"] == "Bearer AIza-test-key-123"
    assert sent["body"]["model"] == GEMINI_DEFAULT_MODEL


async def test_google_request_leaves_room_for_thinking_and_skips_json_mode(recorder):
    # Gemini 3 models always think, and thinking counts against the output limit; the
    # OpenAI-compatible docs only document schema-based structured output, not json_object.
    payload = {"provider": "google", "model": GEMINI_DEFAULT_MODEL, "api_key": "AIza-test-key-123", "topic": "Photosynthesis"}
    async with await _client() as client:
        await client.post("/api/ai/generate-quiz", json=payload)
    body = recorder.sent[0]["body"]
    assert body["reasoning_effort"] == "low"
    assert body["max_tokens"] >= 8192
    assert "response_format" not in body


async def test_request_without_provider_uses_google(recorder):
    payload = {"api_key": "AIza-test-key-123", "topic": "Photosynthesis"}
    async with await _client() as client:
        resp = await client.post("/api/ai/generate-quiz", json=payload)
    assert resp.status_code == 200, resp.text
    sent = recorder.sent[0]
    assert sent["url"] == f"{GEMINI_BASE}/chat/completions"
    assert sent["body"]["model"] == GEMINI_DEFAULT_MODEL


async def test_other_providers_keep_their_request_shape(recorder):
    payload = {"provider": "groq", "model": "qwen/qwen3-32b", "api_key": "gsk-test-key-123", "topic": "Photosynthesis"}
    async with await _client() as client:
        await client.post("/api/ai/generate-quiz", json=payload)
    body = recorder.sent[0]["body"]
    assert body["response_format"] == {"type": "json_object"}
    assert "reasoning_effort" not in body
    assert body["max_tokens"] == 4096
