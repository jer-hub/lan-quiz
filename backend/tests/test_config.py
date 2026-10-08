"""Fail-fast config: default secret refused unless explicitly allowed."""

import pytest

from app.config import DEFAULT_JWT_SECRET, Settings


def test_default_secret_refused():
    s = Settings(jwt_secret=DEFAULT_JWT_SECRET, allow_default_secret=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        s.ensure_secure()


def test_default_secret_allowed_for_dev():
    s = Settings(jwt_secret=DEFAULT_JWT_SECRET, allow_default_secret=True)
    s.ensure_secure()  # no raise


def test_custom_secret_passes():
    s = Settings(jwt_secret="strong-random-value", allow_default_secret=False)
    s.ensure_secure()


def test_loopback_detection():
    assert Settings(host_ip="localhost").host_ip_is_loopback
    assert Settings(host_ip="127.0.0.1").host_ip_is_loopback
    assert not Settings(host_ip="192.168.1.42").host_ip_is_loopback
