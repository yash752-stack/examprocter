from __future__ import annotations

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    password_bytes = password.encode("utf-8")
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password_bytes,
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return f"{salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, digest_hex = password_hash.split("$", 1)
    except ValueError:
        return False

    expected = bytes.fromhex(digest_hex)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(candidate, expected)


def issue_auth_token() -> str:
    return secrets.token_urlsafe(32)


def issue_session_token() -> str:
    return secrets.token_urlsafe(24)
