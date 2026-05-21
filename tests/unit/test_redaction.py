import pytest

from app.infra.redaction import redact

pytestmark = pytest.mark.unit

_CASES = [
    (
        "fake API key",
        "api_key=fake_api_key_1234567890abcdef",
        "fake_api_key_1234567890abcdef",
    ),
    (
        "fake GitHub token",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ12345678901",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ12345678901",
    ),
    (
        "authorization header bearer",
        "Authorization: Bearer fake-bearer-token-123",
        "fake-bearer-token-123",
    ),
    (
        "password assignment",
        "password=hunter2 in config",
        "hunter2",
    ),
    (
        "email address",
        "user email is dina@example.com in log",
        "dina@example.com",
    ),
]


@pytest.mark.parametrize("description,text,secret", _CASES)
def test_redaction_removes_secret(description: str, text: str, secret: str):
    result = redact(text)
    assert secret not in result, f"[{description}] secret leaked in output: {result!r}"
    assert "[REDACTED]" in result
