# Classification Golden Set

## Status

**PENDING CURATION** — `classification_golden_candidates.csv` is a candidate pool.
`gold_label` must be manually verified before this file becomes the official golden set.

## Purpose

A hand-curated 25-issue golden set for evaluation of the four-class classifier:
`bug` / `feature` / `docs` / `question` on `kubernetes/kubernetes` issues.

Separate from the official test split (`data/processed/test.csv`).
Used for human-in-the-loop spot-check and presentation demos.

## Files

| File | Status | Description |
|---|---|---|
| `classification_golden_candidates.csv` | **needs curation** | 48 candidates (12/class), suggested labels, blank gold fields |
| `classification_golden.jsonl` | not yet created | final 25 curated examples with confirmed gold_label |

## Curation workflow

1. Open `classification_golden_candidates.csv` in a spreadsheet or text editor.
2. Read each issue's `title` and `body_preview` (and follow `html_url` if needed).
3. Fill in `gold_label` — must be one of: `bug`, `feature`, `docs`, `question`.
4. Optionally fill `curator_notes` with the reason if `gold_label` differs from `suggested_label`.
5. Select **exactly 25 rows** — aim for roughly 6–7 per class.
   - Prefer single-label issues (where `raw_labels` contains exactly one target label).
   - Prefer issues with clear, unambiguous wording in title and body.
6. Save selected rows as `evals/golden/classification_golden.jsonl` (one JSON object per line).

## Candidate generation

Script: `ml/create_classification_golden_candidates.py`

```bash
uv run python ml/create_classification_golden_candidates.py
```

Sources `data/raw/kubernetes_issues.jsonl`.
Excludes all issue_numbers in the official train/val/test splits.
Selects 12 candidates per class spread chronologically.
Prefers single-label issues (no multi-label conflict) for annotation clarity.

## Candidate pool summary

Generated on the official dataset (data/raw/kubernetes_issues.jsonl, 3923 issues).
Excluded 2400 issue_numbers already in official splits.

| Class | Candidates available | Selected for review |
|---|---|---|
| bug | 797 | 12 |
| feature | 388 | 12 |
| docs | 306 | 12 |
| question | 19 | 12 |

## WARNING

> **gold_label must be manually verified before this file becomes the official golden set.**

Do not use `suggested_label` as a substitute for `gold_label`.
`suggested_label` is derived automatically from GitHub labels and may be wrong.
