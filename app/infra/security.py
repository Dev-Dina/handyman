from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import secrets
import time

from app.domain.auth import InvalidCredentialsError

# --- Constants ---

_PBKDF2_ITERATIONS: int = 260_000
_HASH_ALG: str = "sha256"
TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

_JWT_HEADER: str = (
    base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    .rstrip(b"=")
    .decode()
)


# --- Password hashing (PBKDF2-SHA256, stdlib only) ---


def hash_password(plain: str) -> str:
    """Return PBKDF2-SHA256 digest in iter$salt$hash format."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALG, plain.encode(), salt.encode(), _PBKDF2_ITERATIONS
    )
    return f"{_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    """Return True iff plain matches the stored hash."""
    try:
        iters_str, salt, stored_hash = stored.split("$", 2)
        dk = hashlib.pbkdf2_hmac(
            _HASH_ALG, plain.encode(), salt.encode(), int(iters_str)
        )
        return _hmac.compare_digest(dk.hex(), stored_hash)
    except Exception:
        return False


# --- JWT (HS256, stdlib only) ---


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def create_access_token(
    payload: dict, secret: str, expire_minutes: int = TOKEN_EXPIRE_MINUTES
) -> str:
    """Create a signed HS256 JWT. Never logs secret or payload."""
    now = int(time.time())
    claims = {**payload, "iat": now, "exp": now + expire_minutes * 60}
    body = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{_JWT_HEADER}.{body}"
    sig = _hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_access_token(token: str, secret: str) -> dict:
    """Verify and decode a signed HS256 JWT.

    Raises InvalidCredentialsError on malformed token, bad signature, or expiry.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidCredentialsError("malformed token")
    header_b64, body_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{body_b64}"
    expected_sig = _hmac.new(
        secret.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        raise InvalidCredentialsError("invalid signature")
    if not _hmac.compare_digest(expected_sig, actual_sig):
        raise InvalidCredentialsError("invalid signature")
    try:
        claims = json.loads(_b64url_decode(body_b64))
    except Exception:
        raise InvalidCredentialsError("malformed token payload")
    if claims.get("exp", 0) < time.time():
        raise InvalidCredentialsError("token expired")
    return claims
