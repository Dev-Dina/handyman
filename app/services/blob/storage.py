"""Blob storage service — business-level upload helpers.

All uploads go through MinioClient (app/infra/minio_client.py).
Content is redacted before upload where it may contain user-supplied text.
No HTTPException raised here. No SQLAlchemy. No Torch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.infra.redaction import redact
from app.infra.tracing import get_tracer
from app.services.blob.config import (
    BUCKET_ARTIFACTS,
    CONTENT_TYPE_BINARY,
    PREFIX_RETRIEVAL_SNAPSHOTS,
)


def upload_json(
    client,
    payload: dict,
    bucket: str,
    object_name: str,
) -> int:
    """Upload a JSON payload to MinIO. Returns bytes uploaded."""
    tracer = get_tracer()
    with tracer.start_span("blob.upload_json") as span:
        span.set_attribute("bucket", bucket)
        span.set_attribute("object_name", object_name)
        size = client.upload_json(payload, bucket, object_name)
        span.set_attribute("size_bytes", str(size))
        span.set_attribute("status", "ok")
        return size


def upload_file(
    client,
    local_path: Path,
    bucket: str,
    object_name: str,
    content_type: str = CONTENT_TYPE_BINARY,
) -> int:
    """Upload a local file to MinIO. Returns bytes uploaded.

    Raises FileNotFoundError if local_path does not exist.
    Raises MinioUnavailableError on connection/upload failure.
    """
    tracer = get_tracer()
    with tracer.start_span("blob.upload_file") as span:
        span.set_attribute("bucket", bucket)
        span.set_attribute("object_name", object_name)
        size = client.upload_file(
            local_path, bucket, object_name, content_type=content_type
        )
        span.set_attribute("size_bytes", str(size))
        span.set_attribute("status", "ok")
        return size


def upload_retrieval_snapshot(
    client,
    *,
    question: str,
    retriever_used: str,
    query_transform_used: str,
    top_k: int,
    chunks: list[dict],
    conversation_id: str = "",
    trace_id: str = "",
    bucket: str = BUCKET_ARTIFACTS,
    prefix: str = PREFIX_RETRIEVAL_SNAPSHOTS,
) -> dict:
    """Build and upload a retrieval snapshot for a single RAG query.

    The question is redacted before upload.
    Chunk content/text is not included — only IDs, source types, and scores.
    If MinIO is unavailable the caller must catch MinioUnavailableError.
    """
    tracer = get_tracer()
    with tracer.start_span("blob.snapshot_retrieval") as span:
        span.set_attribute("bucket", bucket)
        span.set_attribute("retriever_used", retriever_used)
        span.set_attribute("chunk_count", str(len(chunks)))

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        object_name = f"{prefix}{ts}_{conversation_id or 'anon'}.json"

        snapshot: dict = {
            "conversation_id": conversation_id or "",
            "question": redact(question),
            "retriever_used": retriever_used,
            "query_transform_used": query_transform_used,
            "top_k": top_k,
            "chunk_ids": [c.get("chunk_id", "") for c in chunks],
            "source_types": sorted({c.get("source_type", "") for c in chunks}),
            "scores": [c.get("score", 0.0) for c in chunks],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        size = client.upload_json(snapshot, bucket, object_name)

        span.set_attribute("object_name", object_name)
        span.set_attribute("size_bytes", str(size))
        span.set_attribute("status", "ok")

        return {"object_name": object_name, "size_bytes": size, "status": "uploaded"}
