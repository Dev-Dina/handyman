# RAG Golden Set

## Status

**PENDING** — golden set will be created in RAG-3, after chunking is finalized.

## Purpose

A 25-example hand-curated golden set for evaluating the RAG pipeline
(retrieval quality + answer quality) on kubernetes/kubernetes issues.

Separate from the classifier golden set (`evals/golden/classification_golden.jsonl`).

---

## Final Schema

Each record in `rag_golden.jsonl` must have:

| Field | Type | Description |
|---|---|---|
| `question` | string | The maintainer question to answer |
| `ideal_answer` | string | Expected answer text (hand-written) |
| `ground_truth_chunk_ids` | list[str] | IDs of chunks that contain the answer |
| `source_urls` | list[str] | GitHub or docs URLs for the ground-truth source |
| `notes` | string | Curator notes: why this question, ambiguities |
| `hand_labeled_for_judge_check` | bool | True if used for LLM judge agreement audit |

Example:
```json
{
  "question": "Why does a pod with OOMKilled status not restart automatically?",
  "ideal_answer": "By default, restartPolicy is Always, but OOMKilled pods restart only if the container's restart policy allows it and the node has available memory.",
  "ground_truth_chunk_ids": ["chunk_0042", "chunk_0117"],
  "source_urls": ["https://github.com/kubernetes/kubernetes/issues/98765"],
  "notes": "Classic question from kind/support issues; ground truth in both issue body and comment",
  "hand_labeled_for_judge_check": true
}
```

---

## Requirements

- **25 total examples** across question types: bug triage, feature requests, docs clarification, how-to.
- **At least 5 examples** must have `hand_labeled_for_judge_check: true` for LLM judge agreement audits.
- All `ground_truth_chunk_ids` must exist in the finalized chunk corpus (`data/rag/chunks/`).
- No issue_number from the RAG golden set may overlap with the classifier splits (`data/processed/`).

---

## Files

| File | Status | Description |
|---|---|---|
| `rag_golden_candidates.csv` | PENDING | Generated candidate pool (RAG-3) |
| `rag_golden.jsonl` | PENDING | Official 25-example golden set (after curation) |

---

## Generation Workflow

1. After corpus and chunks exist (RAG-2), run `ml/rag_create_golden_candidates.py`.
2. Review candidates — write `question` and `ideal_answer` for each.
3. Identify which chunks contain the answer — write `ground_truth_chunk_ids`.
4. Select 25 examples, at least 5 with `hand_labeled_for_judge_check: true`.
5. Run `ml/finalize_rag_golden.py` to validate and write `rag_golden.jsonl`.

## Constraint

> **ground_truth_chunk_ids must point to real chunks in the finalized corpus.**
> Do not create the golden set before chunking is complete.
