"""Upload key report and eval artifacts to MinIO.

Uploads:
  - reports/artifact_manifest.json
  - reports/rag/api_eval_report.json
  - reports/classifier_three_way_comparison.json / .csv
  - eval_thresholds.yaml

Missing files are skipped. MinIO unavailable → non-zero exit.
Writes reports/blob/upload_summary.json after each run.

Usage:
    python -m pipelines.blob.upload_artifacts
    python -m pipelines.blob.upload_artifacts --dry-run
    python -m pipelines.blob.upload_artifacts --include-model-artifacts
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.paths import PROJECT_ROOT, REPORTS_DIR
from app.domain.blob import MinioUnavailableError
from app.infra.minio_client import get_minio_client
from app.services.blob.config import (
    BUCKET_ARTIFACTS,
    BUCKET_EVALS,
    CONTENT_TYPE_BINARY,
    CONTENT_TYPE_CSV,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_YAML,
    PREFIX_EVAL_REPORTS,
    PREFIX_MODEL_ARTIFACTS,
    UPLOAD_SUMMARY_PATH,
)
from app.services.blob.storage import upload_file

# ---------------------------------------------------------------------------
# Report artifacts — (local_path, content_type, bucket, object_name)
# ---------------------------------------------------------------------------
_REPORT_ARTIFACTS: list[tuple[Path, str, str, str]] = [
    (
        REPORTS_DIR / "artifact_manifest.json",
        CONTENT_TYPE_JSON,
        BUCKET_EVALS,
        f"{PREFIX_EVAL_REPORTS}artifact_manifest.json",
    ),
    (
        REPORTS_DIR / "rag" / "api_eval_report.json",
        CONTENT_TYPE_JSON,
        BUCKET_EVALS,
        f"{PREFIX_EVAL_REPORTS}api_eval_report.json",
    ),
    (
        REPORTS_DIR / "classifier_three_way_comparison.json",
        CONTENT_TYPE_JSON,
        BUCKET_EVALS,
        f"{PREFIX_EVAL_REPORTS}classifier_three_way_comparison.json",
    ),
    (
        REPORTS_DIR / "classifier_three_way_comparison.csv",
        CONTENT_TYPE_CSV,
        BUCKET_EVALS,
        f"{PREFIX_EVAL_REPORTS}classifier_three_way_comparison.csv",
    ),
    (
        PROJECT_ROOT / "eval_thresholds.yaml",
        CONTENT_TYPE_YAML,
        BUCKET_EVALS,
        f"{PREFIX_EVAL_REPORTS}eval_thresholds.yaml",
    ),
]

# ---------------------------------------------------------------------------
# Model artifact manifests — only uploaded with --include-model-artifacts
# ---------------------------------------------------------------------------
_MODEL_ARTIFACTS: list[tuple[Path, str, str, str]] = [
    (
        PROJECT_ROOT / "artifacts" / "classical" / "best_model.joblib",
        CONTENT_TYPE_BINARY,
        BUCKET_ARTIFACTS,
        f"{PREFIX_MODEL_ARTIFACTS}classical/best_model.joblib",
    ),
]


def _upload_batch(
    client,
    artifacts: list[tuple[Path, str, str, str]],
    *,
    dry_run: bool,
) -> list[dict]:
    results: list[dict] = []
    for local_path, content_type, bucket, object_name in artifacts:
        entry: dict = {"file": str(local_path), "object": f"{bucket}/{object_name}"}
        if not local_path.exists():
            entry["status"] = "skipped"
            entry["reason"] = "not_found"
            results.append(entry)
            continue
        if dry_run:
            entry["status"] = "dry_run"
            entry["size_bytes"] = local_path.stat().st_size
            results.append(entry)
            continue
        try:
            client.ensure_bucket(bucket)
            size = upload_file(
                client, local_path, bucket, object_name, content_type=content_type
            )
            entry["status"] = "uploaded"
            entry["size_bytes"] = size
        except MinioUnavailableError as exc:
            entry["status"] = "failed"
            entry["error"] = f"{type(exc).__name__}: MinIO unavailable"
        results.append(entry)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload artifacts and eval reports to MinIO."
    )
    parser.add_argument(
        "--include-model-artifacts",
        action="store_true",
        help="Also upload model artifact files (can be large).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files without uploading.",
    )
    args = parser.parse_args()

    try:
        client = get_minio_client()
    except Exception as exc:
        print(f"ERROR: Could not initialise MinIO client: {type(exc).__name__}")
        raise SystemExit(1)

    artifacts = list(_REPORT_ARTIFACTS)
    if args.include_model_artifacts:
        artifacts.extend(_MODEL_ARTIFACTS)

    results = _upload_batch(client, artifacts, dry_run=args.dry_run)

    summary: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "uploads": results,
        "total": len(results),
        "uploaded": sum(1 for r in results if r["status"] == "uploaded"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
    }

    summary_path = PROJECT_ROOT / UPLOAD_SUMMARY_PATH
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Upload summary: {summary_path}")
    print(
        f"  uploaded={summary['uploaded']}  "
        f"skipped={summary['skipped']}  "
        f"failed={summary['failed']}"
    )

    if summary["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
