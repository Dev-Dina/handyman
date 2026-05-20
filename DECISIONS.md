# Decisions

## Dataset

**Chosen repo:** kubernetes/kubernetes

**Why:**
kubernetes/kubernetes is a large, actively maintained infrastructure project with
tens of thousands of closed issues. Maintainers apply structured `kind/*` labels
consistently, yielding clean signal for four target classes. The label set is
simple (4 target labels, exact match, no normalisation needed) and each class
has thousands of examples, giving a balanced supervised dataset.

## Label mapping

**Status:** Draft. Will be confirmed after EDA review.

Final classes: bug / feature / docs / question

| GitHub label         | Project class |
|----------------------|---------------|
| kind/bug             | bug           |
| kind/feature         | feature       |
| kind/documentation   | docs          |
| kind/support         | question      |

Only issues carrying at least one of these four labels enter the supervised dataset.
Issues with none of these labels are dropped and recorded in EDA reports.

## Multi-label honesty policy

Multi-label issues are **not hidden** and **not silently dropped**.

1. Every issue's full GitHub label set is stored in `raw_labels` in the JSONL file.
2. For each issue, the set of *target* labels found is computed (e.g. kind/bug + kind/feature).
3. If exactly one target label is present → class assigned directly, no conflict.
4. If multiple target labels are present → deterministic conflict resolution is applied
   (see priority below) AND the issue is written to `reports/multilabel_conflicts.csv`
   with: issue_number, title, target_labels_found, chosen_final_label, resolution_reason, html_url.
5. The split report records: total conflict count, per-combination counts, examples,
   and the conflict policy string.

**Why transparency matters:**
Hiding conflicts (e.g. by only fetching with negative label filters) would undercount
real dataset ambiguity and make evaluation results misleading. Recording conflicts lets
us audit resolution quality and revisit the priority later.

## Conflict priority

bug > docs > feature > question

| Priority | Class       | Reason                                                              |
|----------|-------------|---------------------------------------------------------------------|
| 1        | bug         | Highest operational severity; a bug report is distinct              |
| 2        | docs        | Distinct assignment type; must not be swallowed by feature/support  |
| 3        | feature     | Product/change request; lower urgency than bugs or doc fixes        |
| 4        | question    | Weakest signal; support/usage questions are least actionable        |

## Fetching strategy

Uses GitHub Search API with per-class label queries:

    label:"kind/bug"           → up to 1000 closed issues
    label:"kind/feature"       → up to 1000 closed issues
    label:"kind/documentation" → up to 1000 closed issues
    label:"kind/support"       → up to 1000 closed issues

Issues appearing in multiple queries are deduplicated by issue_number.
GitHub always returns the full label set in the API response, so first-seen wins.
PRs are excluded by the `is:issue` Search API qualifier.
Negative label filters are NOT used — overlaps are preserved and reported.

## Split strategy

Time-based stratified split per class:
- Within each class, sort by created_at ascending.
- Oldest 70% → train, next 15% → val, newest 15% → test.
- Guarantees test is strictly newer than train within every class.
- Both global and per-class temporal order are validated and reported.
- Val/test fractions configurable via --val-frac / --test-frac flags.

**Note:** Final split will be run only after EDA confirms label distribution is acceptable.

**Temporal disclaimer:** A strict global chronological split caused the docs class to disappear from validation/test because all docs issues predate the global val/test cutoff. We therefore used per-class chronological stratification to preserve all four classes for macro-F1 and per-class F1 evaluation. Test examples are newer than train examples within each class, but not globally newer across all classes.

## Unlabeled / unmapped handling

Issues with no target label are:
- Excluded from the supervised train/val/test splits.
- Sampled and written to `reports/unlabeled_issues_sample.csv` for inspection.
- Counted in `reports/label_eda.json` under `unlabeled_count`.

## Classical model

Best model: LogisticRegression (TF-IDF).
val_macro_f1: 0.701875 — test_macro_f1: 0.693839.
Artifacts: artifacts/classical/best_model.*

## Support-only augmentation experiment (ablation — not adopted)

**What was tried:**
Fetched additional `kind/support` issues via `--supplement-label kind/support` to address the 405 issues lost to multi-label conflict resolution.
Resulted in `data/raw/kubernetes_issues_augmented.jsonl` (4 304 unique issues) and splits in `data/processed_augmented/`.

**Results:**

| Metric | Original split | Augmented split |
|---|---|---|
| Val macro-F1 | — | 0.840244 |
| Test macro-F1 | 0.693839 | 0.680766 |
| Question test F1 | — | 0.272727 |

**Decision: do not adopt.**
The augmented split improved validation macro-F1 but degraded test macro-F1 and left the question class weak (test F1 0.272727). The gap between val and test F1 (0.84 → 0.68) signals overfitting to the augmented distribution. The original balanced split (420/class train, 90/class val/test) remains the official classifier dataset.

**Official dataset:**
- `data/processed/train.csv` — 1 680 rows, 420/class
- `data/processed/val.csv` — 360 rows, 90/class
- `data/processed/test.csv` — 360 rows, 90/class

Augmented data and splits archived under `data/experiments/failed/support_augmented/` and `reports/experiments/failed/support_augmented/`.

## Classifier dataset — final decision (LOCKED)

**Official dataset:** `data/processed/` — 420/class train, 90/class val/test. Locked.

Three alternative preprocessing/data strategies were evaluated and rejected:

| Experiment | test_macro_f1 | vs baseline | Decision |
|---|---|---|---|
| Original (baseline) | 0.693839 | — | **OFFICIAL** |
| Support-only augmentation | 0.680766 | -0.013 | Rejected — val/test gap, weak question F1 |
| Cleaned splits (processed_cleaned) | 0.693839 | 0.000 | Rejected — no improvement |
| Strict text preprocessing | 0.637926 | -0.056 | Rejected — worse across all models |

**Ruling:** Original balanced split with default `model_text` preprocessing is the official classifier dataset. All experiments archived under `data/experiments/failed/` and `reports/experiments/failed/`.

Transformer and LLM baselines must use `data/processed/` only.

## Failed experiment archive locations

| Experiment | Data | Reports |
|---|---|---|
| Support-only augmentation | `data/experiments/failed/support_augmented/` | `reports/experiments/failed/support_augmented/` |
| Cleaned splits | `data/experiments/failed/cleaned_splits/` | `reports/experiments/failed/cleaned_splits/` |
| Strict text | `data/experiments/failed/strict_text/` | `reports/experiments/failed/strict_text/` |

Source scripts remain in `ml/` as documentation (do not delete).

## Fine-tuned transformer

Architecture: distilbert-base-uncased (full) / prajjwal1/bert-tiny (smoke).
Labels: bug / docs / feature / question (same 4 classes, same IDs).

## LLM baseline
TODO

## Deployment model choice
TODO after metrics.

## Embedding model comparison
TODO

## Chunking strategy
TODO

## Hybrid retrieval weighting
TODO

## Reranker
TODO

## Query transformation
TODO

## Memory choice
Chosen long-term memory type: episodic

Reason:
Episodic memory is easiest to demonstrate across conversations and fits maintainer
preferences/actions.

## Redis TTL
Short-term memory TTL: 24 hours

Reason:
Preserves active triage context across breaks without keeping temporary debugging
context forever.

## Tracing backend
TODO

## Widget bundle target
TODO
