"""Pytest bootstrap: allow default secret for unit tests."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("ALLOW_DEFAULT_SECRET", "true")
