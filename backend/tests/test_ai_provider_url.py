"""Custom AI provider URL check: https only, no internal targets, fixed error text.

Seams: the HTTP endpoint through an ASGI client. DNS (socket.getaddrinfo) and the
provider call (httpx.AsyncClient) are faked, so no real network traffic happens.
"""

import json
import socket

import httpx
import pytest
from httpx import ASGITransport
from httpx import AsyncClient as RealAsyncClient

from app.auth import require_teacher
from app.config import settings
from app.main import fastapi_app
from app.models import User

ENDPOINT = "/api/ai/generate-quiz"
PUBLIC_IP = "93.184.216.34"

# Hostname -> resolved addresses. Anything not listed fails to resolve, so a
# test can never reach a real DNS server by accident.
DNS: dict[str, list[str]] = {
    "api.example.com": [PUBLIC_IP],
    "ai.internal.example": ["10.0.0.5"],
    "lan.example": ["192.168.1.20"],
    "link.example": ["169.254.169.254"],
    "loop.example": ["::1"],
    "mapped.example": ["::ffff:127.0.0.1"],
    "zero.example": ["0.0.0.0"],
    "localhost": ["127.0.0.1"],
}


def _fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    addrs = DNS.get(host)
    if addrs is None:
        raise socket.gaierror(f"no fake DNS entry for {host}")
    out = []
    for ip in addrs:
        fam = socket.AF_INET6 if ":" in ip else socket.AF_INET
        sockaddr = (ip, 443, 0, 0) if fam == socket.AF_INET6 else (ip, 443)
        out.append((fam, socket.SOCK_STREAM, 6, "", sockaddr))
    return out


QUIZ_JSON = json.dumps(
    {
        "title": "Plants",
        "description": "",
        "questions": [
            {
                "text": f"Question {i}?",
                "options": ["A", "B", "C"],
                "correct_indices": [1],
                "time_limit": 20,
            }
            for i in range(3)
        ],
    }
)


class FakeProvider:
    """Stands in for httpx.AsyncClient inside the AI router."""

    response: httpx.Response | None = None
    calls: list[str] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        FakeProvider.calls.append(url)
        return FakeProvider.response


def _ok_response():
    body = {"choices": [{"message": {"content": QUIZ_JSON}}]}
    return httpx.Response(200, json=body, request=httpx.Request("POST", "https://x"))


@pytest.fixture
def provider(monkeypatch):
    FakeProvider.calls = []
    FakeProvider.response = _ok_response()
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(httpx, "AsyncClient", FakeProvider)
    monkeypatch.setattr(settings, "allow_private_ai_providers", False)
    fastapi_app.dependency_overrides[require_teacher] = lambda: User(id=1)
    yield FakeProvider
    fastapi_app.dependency_overrides.pop(require_teacher, None)


def _payload(base_url, provider_id="custom"):
    return {
        "provider": provider_id,
        "model": "test-model",
        "api_key": "sk-test-12345678",
        "base_url": base_url,
        "topic": "Photosynthesis basics",
    }


async def _post(payload):
    transport = ASGITransport(app=fastapi_app)
    async with RealAsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(ENDPOINT, json=payload)


async def test_http_url_refused_before_any_request(provider):
    resp = await _post(_payload("http://api.example.com/v1"))
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"]
    assert provider.calls == []


@pytest.mark.parametrize(
    "base_url",
    [
        "https://127.0.0.1/v1",  # loopback literal
        "https://localhost/v1",  # loopback by name
        "https://ai.internal.example/v1",  # public-looking name, private address
        "https://lan.example/v1",  # private LAN address
        "https://link.example/v1",  # link-local (cloud metadata address)
        "https://loop.example/v1",  # IPv6 loopback
        "https://mapped.example/v1",  # IPv4-mapped IPv6 loopback
        "https://zero.example/v1",  # unspecified address
    ],
)
async def test_internal_host_refused_without_flag(provider, base_url):
    resp = await _post(_payload(base_url))
    assert resp.status_code == 400
    assert provider.calls == []


async def test_internal_host_allowed_with_flag(provider, monkeypatch):
    monkeypatch.setattr(settings, "allow_private_ai_providers", True)
    resp = await _post(_payload("https://lan.example/v1"))
    assert resp.status_code == 200
    assert provider.calls == ["https://lan.example/v1/chat/completions"]


async def test_public_https_host_allowed(provider):
    resp = await _post(_payload("https://api.example.com/v1"))
    assert resp.status_code == 200
    assert provider.calls == ["https://api.example.com/v1/chat/completions"]


async def test_preset_base_url_override_is_checked(provider):
    # Presets are fixed https hosts, but a supplied base_url still must pass the check.
    resp = await _post(_payload("http://169.254.169.254/latest", provider_id="groq"))
    assert resp.status_code == 400
    assert provider.calls == []


@pytest.mark.parametrize(
    "body_text",
    [
        '{"error": {"message": "INTERNAL-SENTINEL-7731 key sk-leak-abc"}}',
        "RAW-SENTINEL-7731 proxy trace at 10.1.2.3",
    ],
)
async def test_provider_error_body_not_echoed(provider, body_text):
    provider.response = httpx.Response(
        500, content=body_text.encode(), request=httpx.Request("POST", "https://x")
    )
    resp = await _post(_payload("https://api.example.com/v1"))
    assert resp.status_code == 502
    assert "SENTINEL" not in resp.text
    assert "leak" not in resp.text
    assert "10.1.2.3" not in resp.text
    assert "500" in resp.json()["detail"]
