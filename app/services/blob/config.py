"""Runtime constants for the blob/MinIO storage service."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Bucket names
# ---------------------------------------------------------------------------
BUCKET_ARTIFACTS: str = "handyman-artifacts"
BUCKET_EVALS: str = "handyman-evals"

# ---------------------------------------------------------------------------
# Object key prefixes (each ends with /)
# ---------------------------------------------------------------------------
PREFIX_EVAL_REPORTS: str = "eval-reports/"
PREFIX_RETRIEVAL_SNAPSHOTS: str = "retrieval-snapshots/"
PREFIX_MODEL_ARTIFACTS: str = "model-artifacts/"
PREFIX_FIGURES: str = "figures/"

# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------
CONTENT_TYPE_JSON: str = "application/json"
CONTENT_TYPE_CSV: str = "text/csv"
CONTENT_TYPE_YAML: str = "application/yaml"
CONTENT_TYPE_PNG: str = "image/png"
CONTENT_TYPE_BINARY: str = "application/octet-stream"

# ---------------------------------------------------------------------------
# Upload summary output path (relative to project root)
# ---------------------------------------------------------------------------
UPLOAD_SUMMARY_PATH: str = "reports/blob/upload_summary.json"
