"""Unit tests for upload_retrieval_snapshot — retrieval snapshot helper."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.blob import MinioUnavailableError
from app.services.blob.storage import upload_retrieval_snapshot

pytestmark = pytest.mark.unit


def _client(return_size: int = 256) -> MagicMock:
    c = MagicMock()
    c.upload_json.return_value = return_size
    return c


def test_chunk_ids_extracted() -> None:
    client = _client()
    chunks = [
        {"chunk_id": "c1", "source_type": "docs", "score": 0.9},
        {"chunk_id": "c2", "source_type": "issue", "score": 0.7},
    ]
    upload_retrieval_snapshot(
        client,
        question="pod failing",
        retriever_used="hybrid",
        query_transform_used="none",
        top_k=5,
        chunks=chunks,
        bucket="bkt",
        prefix="snaps/",
    )
    payload = client.upload_json.call_args[0][0]
    assert payload["chunk_ids"] == ["c1", "c2"]


def test_source_types_deduplicated() -> None:
    client = _client()
    chunks = [
        {"chunk_id": "c1", "source_type": "docs", "score": 0.9},
        {"chunk_id": "c2", "source_type": "docs", "score": 0.8},
    ]
    upload_retrieval_snapshot(
        client,
        question="kubelet crash",
        retriever_used="tfidf",
        query_transform_used="none",
        top_k=5,
        chunks=chunks,
        bucket="bkt",
        prefix="snaps/",
    )
    payload = client.upload_json.call_args[0][0]
    assert payload["source_types"] == ["docs"]


def test_scores_included() -> None:
    client = _client()
    chunks = [{"chunk_id": "c1", "source_type": "docs", "score": 0.75}]
    upload_retrieval_snapshot(
        client,
        question="test query",
        retriever_used="hybrid",
        query_transform_used="technical_terms",
        top_k=5,
        chunks=chunks,
        bucket="bkt",
        prefix="snaps/",
    )
    payload = client.upload_json.call_args[0][0]
    assert 0.75 in payload["scores"]


def test_object_name_has_prefix() -> None:
    client = _client()
    upload_retrieval_snapshot(
        client,
        question="test",
        retriever_used="hybrid",
        query_transform_used="none",
        top_k=5,
        chunks=[],
        bucket="bkt",
        prefix="retrieval-snapshots/",
    )
    object_name = client.upload_json.call_args[0][2]
    assert object_name.startswith("retrieval-snapshots/")


def test_minio_unavailable_raises() -> None:
    client = MagicMock()
    client.upload_json.side_effect = MinioUnavailableError("down")
    with pytest.raises(MinioUnavailableError):
        upload_retrieval_snapshot(
            client,
            question="test",
            retriever_used="tfidf",
            query_transform_used="none",
            top_k=5,
            chunks=[],
            bucket="bkt",
            prefix="snaps/",
        )


def test_empty_chunks_succeeds() -> None:
    client = _client(return_size=50)
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


def test_question_not_logged_raw() -> None:
    """Snapshot payload must not contain raw secret-looking question text."""
    client = _client()
    upload_retrieval_snapshot(
        client,
        question="Bearer eyJsecrettoken.abc.xyz what is kubelet",
        retriever_used="tfidf",
        query_transform_used="none",
        top_k=5,
        chunks=[],
        bucket="bkt",
        prefix="snaps/",
    )
    payload = client.upload_json.call_args[0][0]
    assert "eyJsecrettoken" not in payload["question"]
