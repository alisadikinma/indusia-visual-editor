"""Phase 13.1 — password hashing primitives.

Wraps `passlib.context.CryptContext(['bcrypt'])` so the rest of the codebase
never imports passlib directly. Three properties matter:

1. `hash_password` is non-deterministic (bcrypt salt per call).
2. `verify_password` accepts the matching plaintext and rejects others.
3. Verifying a non-bcrypt or malformed string returns False, never raises —
   the login endpoint should respond with a 401 envelope, not a 500.
"""

import pytest

from indusia_visual_editor.services.auth.passwords import (
    hash_password,
    verify_password,
)


def test_hash_password_is_non_deterministic():
    h1 = hash_password("correct horse battery staple")
    h2 = hash_password("correct horse battery staple")
    assert h1 != h2, "bcrypt must salt each hash differently"
    assert h1.startswith("$2"), "bcrypt hashes start with $2a$/$2b$/$2y$"


def test_verify_password_accepts_correct_plaintext():
    plain = "indusia-pass-2026"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_rejects_wrong_plaintext():
    hashed = hash_password("indusia-pass-2026")
    assert verify_password("wrong-pass", hashed) is False


def test_verify_password_returns_false_on_malformed_hash():
    """Login should yield 401, not 500, when the stored hash is corrupted."""
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False
