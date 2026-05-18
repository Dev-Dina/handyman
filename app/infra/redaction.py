import re

_REDACTED = "[REDACTED]"

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # OpenAI / Anthropic / generic sk- style API keys
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), _REDACTED),
    # Anthropic sk-ant- style
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), _REDACTED),
    # Generic api_key / apikey assignments (key=value or key: value)
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[^\s,&\"']+"), rf"\1{_REDACTED}"),
    # GitHub classic tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), _REDACTED),
    # GitHub fine-grained PATs
    (re.compile(r"github_pat_[A-Za-z0-9_]{80,}"), _REDACTED),
    # JWT-like: three base64url segments (eyJ...)
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), _REDACTED),
    # Authorization header value (bearer/basic/token)
    (
        re.compile(
            r"(?i)(authorization\s*[=:]\s*)(Bearer\s+\S+|Basic\s+\S+|Token\s+\S+)"
        ),
        rf"\1{_REDACTED}",
    ),
    # password= / password: assignments
    (re.compile(r"(?i)(password\s*[=:]\s*)[^\s,&\"']+"), rf"\1{_REDACTED}"),
    # PEM private key blocks
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        _REDACTED,
    ),
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), _REDACTED),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
