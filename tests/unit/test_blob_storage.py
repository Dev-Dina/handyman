"""Unit tests for app/services/blob/storage.py.

All tests mock MinioClient. No real MinIO, no Docker, no network.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.domain.blob import MinioUnavailableError
from app.services.blob.storage import (
    upload_file,
    upload_json,
    upload_retrieval_snapshot,
)

pytestmark = pytest.mark.unit


def _fake_client(
    *,
    upload_json_return: int = 100,
    upload_file_return: int = 200,
) -> MagicMock:
    client = MagicMock()
    client.upload_json.return_value = upload_json_return
    client.upload_file.return_value = upload_file_return
    return client


# ---------------------------------------------------------------------------
# upload_json
# ---------------------------------------------------------------------------


def test_upload_json_calls_client_upload_json() -> None:
    client = _fake_client()
    size = upload_json(client, {"a": 1}, "bucket", "obj.json")
    client.upload_json.assert_called_once_with({"a": 1}, "bucket", "obj.json")
    assert size == 100


def test_upload_json_propagates_unavailable() -> None:
    client = MagicMock()
    client.upload_json.side_effect = MinioUnavailableError("down")
    with pytest.raises(MinioUnavailableError):
        upload_json(client, {"a": 1}, "bucket", "obj.json")


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


def test_upload_file_returns_size(tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text("{}", encoding="utf-8")
    client = _fake_client(upload_file_return=2)
    size = upload_file(client, f, "bucket", "data.json")
    assert size == 2


def test_upload_file_propagates_file_not_found(tmp_path: Path) -> None:
    client = MagicMock()
    client.upload_file.side_effect = FileNotFoundError("nope")
    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError):
        upload_file(client, missing, "bucket", "obj.json")


def test_upload_file_propagates_unavailable(tmp_path: Path) -> None:
    f = tmp_path / "data.json"
    f.write_text("{}", encoding="utf-8")
    client = MagicMock()
    client.upload_file.side_effect = MinioUnavailableError("down")
    with pytest.raises(MinioUnavailableError):
        upload_file(client, f, "bucket", "data.json")


# ---------------------------------------------------------------------------
# upload_retrieval_snapshot
# ---------------------------------------------------------------------------


def test_snapshot_redacts_question() -> None:
    client = _fake_client()
    upload_retrieval_snapshot(
        client,
        question="api_key=sk-supersecret123456789 what is a pod",
        retriever_used="hybrid",
        query_transform_used="none",
        top_k=5,
        chunks=[{"chunk_id": "c1", "source_type": "docs", "score": 0.9}],
        bucket="bucket",
        prefix="snapshots/",
    )
    payload = client.upload_json.call_args[0][0]
    assert "sk-supersecret123456789" not in payload["question"]
    assert "[REDACTED]" in payload["question"]


def test_snapshot_returns_uploaded_status() -> None:
    client = _fake_client(upload_json_return=512)
    result = upload_retrieval_snapshot(
        client,
        question="what is a pod",
        retriever_used="tfidf",
        query_transform_used="none",
        top_k=3,
        chunks=[],
        bucket="bucket",
        prefix="snaps/",
    )
    assert result["status"] == "uploaded"
    assert result["size_bytes"] == 512
    assert "object_name" in result


def test_snapshot_payload_shape() -> None:
    client = _fake_client()
    upload_retrieval_snapshot(
        client,
        question="what is a pod",
        retriever_used="tfidf",
        query_transform_used="none",
        top_k=3,
        chunks=[{"chunk_id": "c1", "source_type": "docs", "score": 0.8}],
        conversation_id="conv-123",
        trace_id="trace-abc",
        bucket="bucket",
        prefix="snaps/",
    )
    payload = client.upload_json.call_args[0][0]
    assert payload["conversation_id"] == "conv-123"
    assert payload["retriever_used"] == "tfidf"
    assert payload["trace_id"] == "trace-abc"
    assert "chunk_ids" in payload
    assert "scores" in payload
    assert "created_at" in payload
    assert "source_types" in payload


def test_snapshot_propagates_unavailable() -> None:
    client = MagicMock()
    client.upload_json.side_effect = MinioUnavailableError("MinIO down")
    with pytest.raises(MinioUnavailableError):
        upload_retrieval_snapshot(
            client,
            question="test",
            retriever_used="tfidf",
            query_transform_used="none",
            top_k=5,
            chunks=[],
            bucket="bucket",
            prefix="snaps/",
        )


def test_snapshot_empty_chunks_is_valid() -> None:
    client = _fake_client(upload_json_return=80)
    result = upload_retrieval_snapshot(
        client,
        question="empty test",
        retriever_used="tfidf",
        query_transform_used="none",
        top_k=5,
        chunks=[],
        bucket="bkt",
        prefix="snaps/",
    )
    assert result["status"] == "uploaded"


# ---------------------------------------------------------------------------
# Architecture guards
# ---------------------------------------------------------------------------


def test_no_httpexception_import_in_storage() -> None:
    import ast

    from app.services.blob import storage as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = [
        node.names[0].name if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any("HTTPException" in name for name in imported)


def test_no_sqlalchemy_import_in_storage() -> None:
    import ast

    from app.services.blob import storage as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = [
        node.names[0].name if isinstance(node, ast.Import) else (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert not any("sqlalchemy" in name.lower() for name in imported)
