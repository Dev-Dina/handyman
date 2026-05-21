"""RAG-3b: Finalize the RAG golden set from the curated review CSV.

Reads rag_golden_candidates_review.csv, selects rows where
selected_for_final == "yes", validates, and writes rag_golden.jsonl.

Validation gates (all must pass):
  - Exactly 25 selected rows
  - At least 5 rows have hand_labeled_for_judge_check == "true"
  - Expected source mix: docs=5, issue=10, comment=10
  - All required fields non-empty per row
  - No duplicate candidate_id
  - No duplicate question
  - Every ground_truth_chunk_id exists in chunks_section_aware.jsonl
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from app.services.rag.config import (
    RAG_CHUNKS_SECTION_PATH,
    RAG_GOLDEN_DIR,
    RAG_GOLDEN_PATH,
    RAG_GOLDEN_REVIEW_CSV_PATH,
    RAG_GOLDEN_SUMMARY_PATH,
)

_EXPECTED_COUNT = 25
_MIN_JUDGE_CHECK = 5
_EXPECTED_SOURCE_MIX: dict[str, int] = {"docs": 5, "issue": 10, "comment": 10}
_REQUIRED_FIELDS = [
    "candidate_id",
    "question",
    "ideal_answer",
    "ground_truth_chunk_ids",
    "source_urls",
    "source_types",
    "notes",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize the curated RAG golden set review CSV."
    )
    return parser.parse_args()


def _load_valid_chunk_ids() -> frozenset[str]:
    ids: set[str] = set()
    with open(RAG_CHUNKS_SECTION_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["chunk_id"])
    return frozenset(ids)


def _split_field(value: str) -> list[str]:
    return [v.strip() for v in value.split(";") if v.strip()]


def main() -> None:
    _parse_args()

    with open(RAG_GOLDEN_REVIEW_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    selected = [r for r in rows if r.get("selected_for_final", "").strip() == "yes"]

    errors: list[str] = []

    if len(selected) != _EXPECTED_COUNT:
        errors.append(f"expected {_EXPECTED_COUNT} selected rows, got {len(selected)}")

    judge_count = sum(
        1
        for r in selected
        if r.get("hand_labeled_for_judge_check", "").strip().lower() == "true"
    )
    if judge_count < _MIN_JUDGE_CHECK:
        errors.append(
            f"need >= {_MIN_JUDGE_CHECK} hand_labeled_for_judge_check=true, got {judge_count}"
        )

    actual_mix: dict[str, int] = {}
    for r in selected:
        st = r.get("source_types", "").strip()
        actual_mix[st] = actual_mix.get(st, 0) + 1
    if actual_mix != _EXPECTED_SOURCE_MIX:
        errors.append(f"source mix {actual_mix} != expected {_EXPECTED_SOURCE_MIX}")

    for r in selected:
        cid = r.get("candidate_id", "")
        for field in _REQUIRED_FIELDS:
            if not r.get(field, "").strip():
                errors.append(f"{cid}: empty required field '{field}'")

    seen_ids: set[str] = set()
    for r in selected:
        cid = r["candidate_id"]
        if cid in seen_ids:
            errors.append(f"duplicate candidate_id: {cid}")
        seen_ids.add(cid)

    seen_questions: set[str] = set()
    for r in selected:
        q = r["question"].strip()
        if q in seen_questions:
            errors.append(f"duplicate question: {q[:80]}")
        seen_questions.add(q)

    valid_chunk_ids = _load_valid_chunk_ids()
    invalid_refs: list[str] = []
    for r in selected:
        for chunk_id in _split_field(r["ground_truth_chunk_ids"]):
            if chunk_id not in valid_chunk_ids:
                invalid_refs.append(chunk_id)
                errors.append(f"invalid ground_truth_chunk_id: {chunk_id}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    records = []
    for idx, row in enumerate(selected):
        records.append(
            {
                "golden_id": f"rag_gold_{idx:04d}",
                "candidate_id": row["candidate_id"],
                "question": row["question"].strip(),
                "ideal_answer": row["ideal_answer"].strip(),
                "ground_truth_chunk_ids": _split_field(row["ground_truth_chunk_ids"]),
                "source_urls": _split_field(row["source_urls"]),
                "source_types": _split_field(row["source_types"]),
                "issue_numbers": _split_field(row.get("issue_numbers", "")),
                "notes": row["notes"].strip(),
                "hand_labeled_for_judge_check": (
                    row.get("hand_labeled_for_judge_check", "false").strip().lower()
                    == "true"
                ),
                "curator_status": "selected",
            }
        )

    RAG_GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAG_GOLDEN_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    unique_chunk_ids: set[str] = set()
    for record in records:
        unique_chunk_ids.update(record["ground_truth_chunk_ids"])

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "row_count": len(records),
        "source_type_counts": actual_mix,
        "hand_labeled_for_judge_check_count": judge_count,
        "unique_ground_truth_chunk_count": len(unique_chunk_ids),
        "invalid_ground_truth_chunk_refs": invalid_refs,
        "source_review_csv": str(RAG_GOLDEN_REVIEW_CSV_PATH),
        "output_jsonl": str(RAG_GOLDEN_PATH),
        "validation_passed": True,
    }
    with open(RAG_GOLDEN_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Written {len(records)} records -> {RAG_GOLDEN_PATH}")
    print(f"  source_types: {actual_mix}")
    print(f"  hand_labeled_for_judge_check: {judge_count}")
    print(f"  unique chunk IDs: {len(unique_chunk_ids)}")
    print(f"Summary: {RAG_GOLDEN_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
