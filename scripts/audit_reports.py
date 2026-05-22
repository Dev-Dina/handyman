"""Inventory reports/ without changing source artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    from app.core.paths import PROJECT_ROOT, REPORTS_DIR
except ImportError:  # pragma: no cover - script fallback for unusual launch contexts

    def _discover_project_root(start: Path) -> Path:
        for candidate in (start, *start.parents):
            if (candidate / "pyproject.toml").is_file():
                return candidate
        raise RuntimeError("Could not discover project root: pyproject.toml not found")

    PROJECT_ROOT = _discover_project_root(Path.cwd().resolve())
    REPORTS_DIR = PROJECT_ROOT / "reports"


STATUSES = {
    "ACTIVE_OFFICIAL",
    "ACTIVE_EVAL",
    "ACTIVE_RUNTIME",
    "FAILED_EXPERIMENT",
    "ARCHIVE",
    "CACHE",
    "UNKNOWN",
}

TRACKS = {
    "classifier",
    "rag",
    "chatbot_memory_widget",
    "blob",
    "ci",
    "figures",
    "failed_experiment",
    "archive",
    "unknown",
}


@dataclass(frozen=True)
class ReportRow:
    path: str
    extension: str
    size_bytes: int
    category: str
    track: str
    status: str
    used_by: str
    notes: str


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _classify(path: Path) -> tuple[str, str, str, str, str]:
    rel = _rel(path)
    name = path.name

    if name == ".gitkeep":
        return (
            "directory_placeholder",
            "unknown",
            "CACHE",
            "git directory retention",
            "Placeholder file used to keep an empty directory.",
        )
    if rel in {"reports/report_inventory.csv", "reports/report_inventory.json"}:
        return (
            "report_inventory",
            "ci",
            "ACTIVE_RUNTIME",
            "reports/README.md; notebooks/00_reports_map.py",
            "Generated report inventory.",
        )
    if rel == "reports/README.md":
        return (
            "report_documentation",
            "ci",
            "ACTIVE_RUNTIME",
            "team review",
            "Explains report categories and retention rules.",
        )
    if rel == "reports/artifact_manifest.json":
        return (
            "project_manifest",
            "ci",
            "ACTIVE_RUNTIME",
            "project tracking",
            "Full path manifest and implementation evidence index.",
        )
    if rel == "reports/classification_eval_report.json":
        return (
            "eval_gate",
            "classifier",
            "ACTIVE_EVAL",
            "CI eval gate",
            "Deterministic LR golden-set eval report.",
        )
    if rel == "reports/rag/api_eval_report.json":
        return (
            "eval_gate",
            "rag",
            "ACTIVE_EVAL",
            "CI eval gate",
            "Deterministic TF-IDF RAG eval report.",
        )
    if rel.startswith("reports/official/figures/"):
        return (
            "presentation_figure",
            "figures",
            "ACTIVE_OFFICIAL",
            "final presentation",
            "Official presentation figure copy.",
        )
    if rel.startswith("reports/experiments/failed/"):
        return (
            "failed_experiment_evidence",
            "failed_experiment",
            "FAILED_EXPERIMENT",
            "decision rationale only",
            "Archived rejected experiment evidence; do not train from this.",
        )
    if rel.startswith(("reports/archive/", "reports/archive_numpy/")):
        return (
            "archive",
            "archive",
            "ARCHIVE",
            "historical evidence only",
            "Archived earlier dataset/report output.",
        )
    if rel.startswith("reports/rag/embeddings_cache/"):
        return (
            "embedding_cache",
            "rag",
            "CACHE",
            "manual retrieval experiments",
            "Embedding cache; not a source of truth.",
        )
    if rel == "reports/blob/upload_summary.json":
        return (
            "runtime_upload_report",
            "blob",
            "ACTIVE_RUNTIME",
            "artifact upload pipeline",
            "Blob upload summary.",
        )
    if rel.startswith("reports/rag/retrieval/") and (
        "comparison" in name or name == "retrieval_runs_summary.csv"
    ):
        return (
            "retrieval_decision_report",
            "rag",
            "ACTIVE_OFFICIAL",
            "RAG decision rationale",
            "Official retrieval comparison evidence.",
        )
    if rel.startswith("reports/rag/") and name in {
        "chunking_report.json",
        "chunking_examples.csv",
        "corpus_collection_report.json",
        "leakage_report.json",
    }:
        return (
            "rag_pipeline_report",
            "rag",
            "ACTIVE_OFFICIAL",
            "RAG decision rationale",
            "Official RAG corpus/chunking evidence.",
        )
    if rel.startswith("reports/rag/retrieval/"):
        return (
            "retrieval_run_output",
            "rag",
            "ACTIVE_RUNTIME",
            "RAG experiments",
            "Individual retrieval run output.",
        )
    if rel.startswith("reports/classical/"):
        return (
            "classifier_report",
            "classifier",
            "ACTIVE_OFFICIAL",
            "classifier decision rationale",
            "Official classical classifier evidence.",
        )
    if rel.startswith("reports/transformer/"):
        return (
            "classifier_report",
            "classifier",
            "ACTIVE_OFFICIAL",
            "classifier decision rationale",
            "Official transformer evidence.",
        )
    if (
        rel.startswith("reports/llm/llama3_full/")
        or rel == "reports/llm/llm_runs_summary.csv"
    ):
        return (
            "classifier_report",
            "classifier",
            "ACTIVE_OFFICIAL",
            "classifier decision rationale",
            "Official LLM baseline evidence.",
        )
    if rel.startswith("reports/llm/"):
        return (
            "llm_cache",
            "classifier",
            "CACHE",
            "manual baseline debugging",
            "Non-official LLM run output.",
        )
    if rel.startswith("reports/figures/"):
        return (
            "working_figure",
            "figures",
            "ACTIVE_RUNTIME",
            "figure generation pipeline",
            "Working figure source; official copies live under reports/official/figures.",
        )
    if rel in {
        "reports/classifier_three_way_comparison.csv",
        "reports/classifier_three_way_comparison.json",
        "reports/kubernetes_class_balance_before_split.csv",
        "reports/kubernetes_label_cooccurrence.csv",
        "reports/kubernetes_label_counts.csv",
        "reports/kubernetes_label_eda.json",
        "reports/kubernetes_multilabel_conflicts.csv",
        "reports/split_report.json",
        "reports/text_quality_report.json",
    }:
        return (
            "classifier_report",
            "classifier",
            "ACTIVE_OFFICIAL",
            "classifier decision rationale",
            "Official dataset/classifier evidence.",
        )
    if rel in {
        "reports/cleaning_audit_report.json",
        "reports/cleaning_examples.csv",
        "reports/transformer_eval.json",
        "reports/transformer_training_history.json",
    }:
        return (
            "superseded_output",
            "classifier",
            "CACHE",
            "historical debugging",
            "Superseded top-level output; canonical run reports live in subdirectories.",
        )
    return (
        "needs_review",
        "unknown",
        "UNKNOWN",
        "manual review",
        "No categorization rule matched.",
    )


def build_inventory() -> list[ReportRow]:
    rows: list[ReportRow] = []
    for path in sorted(REPORTS_DIR.rglob("*")):
        if not path.is_file():
            continue
        category, track, status, used_by, notes = _classify(path)
        if status not in STATUSES or track not in TRACKS:
            raise ValueError(f"Invalid classification for {_rel(path)}")
        rows.append(
            ReportRow(
                path=_rel(path),
                extension=path.suffix.lower() or "(none)",
                size_bytes=path.stat().st_size,
                category=category,
                track=track,
                status=status,
                used_by=used_by,
                notes=notes,
            )
        )
    return rows


def write_inventory(rows: list[ReportRow]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / "report_inventory.csv"
    json_path = REPORTS_DIR / "report_inventory.json"
    fieldnames = [
        "path",
        "extension",
        "size_bytes",
        "category",
        "track",
        "status",
        "used_by",
        "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(row) for row in rows], handle, indent=2)
        handle.write("\n")


def main() -> None:
    rows = build_inventory()
    write_inventory(rows)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    print(f"Wrote {len(rows)} report inventory rows")
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")


if __name__ == "__main__":
    main()
