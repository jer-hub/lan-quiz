"""Cryptographically random codes (game PINs, class join codes, generated passwords)."""

from __future__ import annotations

import secrets


def random_code(length: int, alphabet: str) -> str:
    """Return `length` characters drawn uniformly from `alphabet` using `secrets`."""
    return "".join(secrets.choice(alphabet) for _ in range(length))
