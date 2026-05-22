"""MinIO blob storage adapter.

Credentials come from Vault (minio_access_key, minio_secret_key).
Endpoint comes from MINIO_ENDPOINT env var (default: localhost:9000).
Never logs access_key, secret_key, or connection strings containing credentials.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

from app.domain.blob import MinioUnavailableError

_DEFAULT_ENDPOINT: str = "localhost:9000"
_MINIO_ENDPOINT_ENV: str = "MINIO_ENDPOINT"


class MinioClient:
    """Thin synchronous wrapper around the minio.Minio client.

    Raises MinioUnavailableError on any connection or operation failure.
    Raises FileNotFoundError if a local upload source path does not exist.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        *,
        secure: bool = False,
    ) -> None:
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from minio import Minio  # noqa: PLC0415 — lazy; package may not be installed

                self._client = Minio(
                    self._endpoint,
                    access_key=self._access_key,
                    secret_key=self._secret_key,
                    secure=self._secure,
                )
            except ImportError as exc:
                raise MinioUnavailableError(
                    "minio package not installed — run: uv sync"
                ) from exc
            except Exception as exc:
                raise MinioUnavailableError(
                    f"MinIO client init failed: {type(exc).__name__}"
                ) from exc
        return self._client

    def ensure_bucket(self, bucket_name: str) -> None:
        """Create bucket if it does not already exist."""
        try:
            client = self._get_client()
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
        except MinioUnavailableError:
            raise
        except Exception as exc:
            raise MinioUnavailableError(
                f"ensure_bucket('{bucket_name}') failed: {type(exc).__name__}"
            ) from exc

    def upload_file(
        self,
        local_path: Path,
        bucket: str,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> int:
        """Upload a local file. Returns bytes uploaded.

        Raises FileNotFoundError if local_path does not exist.
        Raises MinioUnavailableError on connection/upload failure.
        """
        if not local_path.exists():
            raise FileNotFoundError(f"Upload source not found: {local_path}")
        try:
            size = local_path.stat().st_size
            self._get_client().fput_object(
                bucket, object_name, str(local_path), content_type=content_type
            )
            return size
        except (MinioUnavailableError, FileNotFoundError):
            raise
        except Exception as exc:
            raise MinioUnavailableError(
                f"upload_file failed: {type(exc).__name__}"
            ) from exc

    def upload_json(self, payload: dict, bucket: str, object_name: str) -> int:
        """Serialize payload to JSON and upload. Returns bytes uploaded."""
        try:
            data = json.dumps(payload, indent=2, default=str).encode("utf-8")
            stream = io.BytesIO(data)
            size = len(data)
            self._get_client().put_object(
                bucket,
                object_name,
                stream,
                size,
                content_type="application/json",
            )
            return size
        except MinioUnavailableError:
            raise
        except Exception as exc:
            raise MinioUnavailableError(
                f"upload_json failed: {type(exc).__name__}"
            ) from exc

    def stat_object(self, bucket: str, object_name: str) -> bool:
        """Return True if the object exists in the bucket, False otherwise."""
        try:
            self._get_client().stat_object(bucket, object_name)
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Module-level singleton — injectable in tests
# ---------------------------------------------------------------------------

_client: MinioClient | None = None


def get_minio_client() -> MinioClient:
    """Return the module-level MinioClient, building it from Vault secrets on first call."""
    global _client
    if _client is None:
        from app.core.config import get_settings  # noqa: PLC0415 — deferred to avoid circular at module load

        settings = get_settings()
        _client = MinioClient(
            endpoint=os.getenv(_MINIO_ENDPOINT_ENV, _DEFAULT_ENDPOINT),
            access_key=settings.secret("minio_access_key"),
            secret_key=settings.secret("minio_secret_key"),
        )
    return _client
