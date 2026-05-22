from __future__ import annotations

MEMORY_ROLE_USER: str = "user"
MEMORY_ROLE_ASSISTANT: str = "assistant"
MEMORY_ROLE_TOOL: str = "tool"
MEMORY_ROLE_MEMORY: str = "memory"

VALID_MEMORY_ROLES: tuple[str, ...] = (
    MEMORY_ROLE_USER,
    MEMORY_ROLE_ASSISTANT,
    MEMORY_ROLE_TOOL,
    MEMORY_ROLE_MEMORY,
)


class RedisUnavailableError(RuntimeError):
    """Raised when the Redis memory store cannot be reached or returns an error."""
