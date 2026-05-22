"""Unit tests for app/infra/minio_client.py.

All tests use mock MinIO objects. No real MinIO, no Docker, no network.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.domain.blob import MinioUnavailableError
from app.infra.minio_client import MinioClient

pytestmark = pytest.mark.unit


def _make_client(
    endpoint: str = "localhost:9000",
    access_key: str = "key",
    secret_key: str = "secret",
) -> MinioClient:
    return MinioClient(endpoint=endpoint, access_key=access_key, secret_key=secret_key)


# ---------------------------------------------------------------------------
# _get_client — lazy init
# ---------------------------------------------------------------------------


def test_minio_package_not_installed_raises_unavailable() -> None:
    client = _make_client()
    with patch.dict("sys.modules", {"minio": None}):
        with pytest.raises(MinioUnavailableError):
            client._get_client()


def test_get_client_returns_cached_instance() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio
    assert client._get_client() is mock_minio


# ---------------------------------------------------------------------------
# ensure_bucket
# ---------------------------------------------------------------------------


def test_ensure_bucket_makes_bucket_when_absent() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = False
    client._client = mock_minio

    client.ensure_bucket("test-bucket")

    mock_minio.make_bucket.assert_called_once_with("test-bucket")


def test_ensure_bucket_skips_make_when_present() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    client._client = mock_minio

    client.ensure_bucket("test-bucket")

    mock_minio.make_bucket.assert_not_called()


def test_ensure_bucket_wraps_exception_as_unavailable() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.bucket_exists.side_effect = Exception("connection refused")
    client._client = mock_minio

    with pytest.raises(MinioUnavailableError):
        client.ensure_bucket("test-bucket")


# ---------------------------------------------------------------------------
# upload_json
# ---------------------------------------------------------------------------


def test_upload_json_calls_put_object() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio

    size = client.upload_json({"key": "value"}, "bucket", "test.json")

    mock_minio.put_object.assert_called_once()
    args = mock_minio.put_object.call_args[0]
    assert args[0] == "bucket"
    assert args[1] == "test.json"
    assert size > 0


def test_upload_json_serializes_payload() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio

    client.upload_json({"hello": "world"}, "bucket", "obj.json")

    stream_arg = mock_minio.put_object.call_args[0][2]
    content = stream_arg.read()
    assert b'"hello"' in content
    assert b'"world"' in content


def test_upload_json_wraps_exception_as_unavailable() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.put_object.side_effect = Exception("timeout")
    client._client = mock_minio

    with pytest.raises(MinioUnavailableError):
        client.upload_json({"a": 1}, "bucket", "obj.json")


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


def test_upload_file_rejects_missing_path(tmp_path: Path) -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio

    missing = tmp_path / "nonexistent.json"

    with pytest.raises(FileNotFoundError):
        client.upload_file(missing, "bucket", "obj.json")


def test_upload_file_calls_fput_object(tmp_path: Path) -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio

    f = tmp_path / "test.json"
    f.write_text('{"x": 1}', encoding="utf-8")

    size = client.upload_file(f, "bucket", "test.json", content_type="application/json")

    mock_minio.fput_object.assert_called_once()
    assert size == f.stat().st_size


def test_upload_file_wraps_exception_as_unavailable(tmp_path: Path) -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.fput_object.side_effect = Exception("timeout")
    client._client = mock_minio

    f = tmp_path / "test.json"
    f.write_text("{}", encoding="utf-8")

    with pytest.raises(MinioUnavailableError):
        client.upload_file(f, "bucket", "test.json")


# ---------------------------------------------------------------------------
# stat_object
# ---------------------------------------------------------------------------


def test_stat_object_returns_true_when_exists() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    client._client = mock_minio

    assert client.stat_object("bucket", "obj.json") is True


def test_stat_object_returns_false_on_error() -> None:
    client = _make_client()
    mock_minio = MagicMock()
    mock_minio.stat_object.side_effect = Exception("not found")
    client._client = mock_minio

    assert client.stat_object("bucket", "missing.json") is False
