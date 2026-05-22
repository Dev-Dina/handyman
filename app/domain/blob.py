"""Domain errors for blob/MinIO storage."""

from __future__ import annotations


class MinioUnavailableError(RuntimeError):
    """Raised when MinIO is unreachable or an upload/download fails."""
