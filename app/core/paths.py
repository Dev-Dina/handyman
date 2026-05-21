"""Canonical project paths.

This module is intentionally lightweight: no settings, Vault, app imports, or
external service dependencies.
"""

from __future__ import annotations

from pathlib import Path


def _discover_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(
        f"Could not discover project root from {start}: pyproject.toml not found"
    )


PROJECT_ROOT = _discover_project_root(Path(__file__).resolve())

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
EVALS_DIR = PROJECT_ROOT / "evals"

RAG_DATA_DIR = DATA_DIR / "rag"
RAG_REPORTS_DIR = REPORTS_DIR / "rag"
RAG_GOLDEN_DIR = EVALS_DIR / "golden" / "rag"

__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "RAW_DATA_DIR",
    "PROCESSED_DATA_DIR",
    "REPORTS_DIR",
    "ARTIFACTS_DIR",
    "EVALS_DIR",
    "RAG_DATA_DIR",
    "RAG_REPORTS_DIR",
    "RAG_GOLDEN_DIR",
]
