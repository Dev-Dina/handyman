"""Build RAG corpus: held-out issue candidates + leakage guard.

Usage:
    python -m pipelines.rag.build_corpus

Outputs:
    data/rag/processed/heldout_issue_candidates.jsonl
    data/rag/corpus_manifest.json
    reports/rag/leakage_report.json
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from app.core.paths import EVALS_DIR, RAW_DATA_DIR
from app.services.rag.config import (
    RAG_CORPUS_MANIFEST_PATH,
    RAG_HELDOUT_CANDIDATES_PATH,
    RAG_LEAKAGE_REPORT_PATH,
    SOURCE_TYPE_ISSUE,
)
from ml.classifier_config import (
    OFFICIAL_TEST_PATH,
    OFFICIAL_TRAIN_PATH,
    OFFICIAL_VAL_PATH,
)

RAW_ISSUES_PATH = RAW_DATA_DIR / "kubernetes_issues.jsonl"
CLASSIFICATION_GOLDEN_PATH = EVALS_DIR / "golden" / "classification_golden.jsonl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build held-out RAG issue candidates and leakage report."
    )
    return parser.parse_args()


def _load_split_ids(csv_path: Path) -> set[str]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        return {row["issue_number"].strip() for row in csv.DictReader(f)}


def _load_golden_ids(jsonl_path: Path) -> set[str]:
    if not jsonl_path.exists():
        return set()
    ids: set[str] = set()
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(str(json.loads(line)["issue_number"]).strip())
    return ids


def _load_raw_issues(jsonl_path: Path) -> list[dict]:
    issues: list[dict] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                issues.append(json.loads(line))
    return issues


def _build_candidates(issues: list[dict], excluded: set[str]) -> list[dict]:
    candidates: list[dict] = []
    for issue in issues:
        issue_id = str(issue.get("issue_number", "")).strip()
        if not issue_id or issue_id in excluded:
            continue
        candidates.append(
            {
                "issue_number": issue_id,
                "source_type": SOURCE_TYPE_ISSUE,
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "html_url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
                "closed_at": issue.get("closed_at", ""),
                "raw_labels": issue.get("raw_labels", []),
            }
        )
    return candidates


def main() -> None:
    _parse_args()

    print("Loading classifier split issue numbers...")
    train_ids = _load_split_ids(OFFICIAL_TRAIN_PATH)
    val_ids = _load_split_ids(OFFICIAL_VAL_PATH)
    test_ids = _load_split_ids(OFFICIAL_TEST_PATH)
    golden_ids = _load_golden_ids(CLASSIFICATION_GOLDEN_PATH)

    excluded = train_ids | val_ids | test_ids | golden_ids
    print(
        f"  train={len(train_ids)}  val={len(val_ids)}  test={len(test_ids)}"
        f"  golden={len(golden_ids)}  total excluded={len(excluded)}"
    )

    print("Loading raw issues...")
    raw_issues = _load_raw_issues(RAW_ISSUES_PATH)
    print(f"  raw_issue_count={len(raw_issues)}")

    print("Building held-out candidates...")
    candidates = _build_candidates(raw_issues, excluded)
    print(f"  heldout_candidate_count={len(candidates)}")

    candidate_ids = {c["issue_number"] for c in candidates}
    overlap_train = len(candidate_ids & train_ids)
    overlap_val = len(candidate_ids & val_ids)
    overlap_test = len(candidate_ids & test_ids)
    overlap_golden = len(candidate_ids & golden_ids)
    leakage_passed = (
        overlap_train == 0
        and overlap_val == 0
        and overlap_test == 0
        and overlap_golden == 0
    )

    # Write held-out JSONL
    RAG_HELDOUT_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_HELDOUT_CANDIDATES_PATH.open("w", encoding="utf-8", newline="") as f:
        for candidate in candidates:
            f.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    print(f"Wrote {len(candidates)} candidates -> {RAG_HELDOUT_CANDIDATES_PATH}")

    # Write leakage report
    leakage_report = {
        "train_count": len(train_ids),
        "val_count": len(val_ids),
        "test_count": len(test_ids),
        "classification_golden_count": len(golden_ids),
        "raw_issue_count": len(raw_issues),
        "heldout_candidate_count": len(candidates),
        "overlap_with_train": overlap_train,
        "overlap_with_val": overlap_val,
        "overlap_with_test": overlap_test,
        "overlap_with_classification_golden": overlap_golden,
        "leakage_passed": leakage_passed,
    }
    RAG_LEAKAGE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_LEAKAGE_REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(leakage_report, f, indent=2)
    print(f"Wrote leakage report -> {RAG_LEAKAGE_REPORT_PATH}")

    if not leakage_passed:
        print("ERROR - leakage detected:", leakage_report)
        sys.exit(1)
    print("Leakage check PASSED - zero overlap with classifier splits.")

    # Write corpus manifest
    corpus_manifest = {
        "status": "local_candidates_only",
        "docs_status": "pending",
        "comments_status": "pending",
        "issue_candidates_path": str(RAG_HELDOUT_CANDIDATES_PATH),
        "leakage_report_path": str(RAG_LEAKAGE_REPORT_PATH),
        "source_policy": (
            "RAG issue corpus must not include classifier train/val/test issues."
        ),
        "next_sources": [
            "project docs",
            "held-out resolved issue comments / maintainer answers",
        ],
    }
    RAG_CORPUS_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CORPUS_MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(corpus_manifest, f, indent=2)
    print(f"Wrote corpus manifest -> {RAG_CORPUS_MANIFEST_PATH}")

    print("\nDONE - RAG-1 corpus build complete.")


if __name__ == "__main__":
    main()
