"""Password hashing primitives.

Thin facade over `passlib.context.CryptContext(['bcrypt'])`. Centralising
the scheme here means rotating to argon2 later only changes this file —
no caller imports passlib directly.

Bcrypt only accepts up to 72 bytes of input; longer inputs are truncated
silently by the library, which is a footgun. We do NOT pre-hash with
SHA-256 to lift the limit because the existing user base (none yet)
hasn't been onboarded; if that changes, add a versioned scheme rather
than retroactively breaking stored hashes.
"""

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plaintext: str) -> str:
    """Return a salted bcrypt hash. Non-deterministic by design."""
    return _pwd.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True iff `plaintext` matches `hashed`. Never raises — a
    malformed or empty stored hash returns False so the login route can
    map all failure paths to a single 401 envelope without leaking which
    side broke."""
    if not hashed:
        return False
    try:
        return _pwd.verify(plaintext, hashed)
    except (ValueError, TypeError):
        return False
