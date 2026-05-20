# Classifier Track Report

_Living document. Updated as the project progresses._

---

## 1. Executive Summary

Four-class issue classifier (bug / docs / feature / question) for `kubernetes/kubernetes`.

| Track | Model | test_macro_f1 | test_accuracy | Status |
|---|---|---|---|---|
| Classical baseline | LogisticRegression (TF-IDF) | **0.6938** | 0.7139 | LOCKED |
| Transformer — best | microsoft/codebert-base | **0.7061** | 0.7500 | LOCKED |
| LLM baseline | llama3:latest (Ollama) | **0.5554** | 0.5850 | LOCKED |

**Final deployment decision: microsoft/codebert-base** (full fine-tune, 3 epochs).  
Beats classical baseline by +0.012 macro-F1. Beats LLM zero-shot by +0.151 macro-F1.  
Operational fallback: LogisticRegression (TF-IDF) — close F1, no GPU required.  
Three-way comparison: `reports/classifier_three_way_comparison.json/csv`.

---

## 2. Official Dataset and Split

| Split | Path | Rows | Per-class |
|---|---|---|---|
| Train | `data/processed/train.csv` | 1 680 | 420 |
| Val | `data/processed/val.csv` | 360 | 90 |
| Test | `data/processed/test.csv` | 360 | 90 |

- Source: `data/raw/kubernetes_issues.jsonl` (3 923 unique issues)
- Strategy: per-class chronological 70/15/15 split
- Test is strictly newer than train within each class
- Global chronological split was rejected: docs class disappeared from val/test because all docs issues predate the global cutoff
- **LOCKED.** Do not replace with any experiment output.

---

## 3. Label Mapping

| GitHub label | Project class |
|---|---|
| kind/bug | bug |
| kind/feature | feature |
| kind/documentation | docs |
| kind/support | question |

Multi-label conflict priority: `bug > docs > feature > question`.  
All conflicts recorded in `reports/kubernetes_multilabel_conflicts.csv` (536 conflicts).

---

## 4. Classifier Constants

All shared labels, official paths, known metrics, and LLM defaults are centralized in `ml/classifier_config.py`. Scripts import from there instead of hardcoding values.

Key exports: `LABELS`, `LABEL_DEFINITIONS`, `OFFICIAL_TRAIN/VAL/TEST_PATH`, `OFFICIAL_*_REPORT_DIR`, `OFFICIAL_FIGURES_DIR`, `CLASSICAL_TEST_MACRO_F1`, `CODEBERT_TEST_MACRO_F1`, `DEFAULT_OLLAMA_*`.

---

## 6. Preprocessing Policy

Official preprocessor: `ml/text_preprocessing.py` → `model_text` column.

- Title and body concatenated with separator
- URLs normalized to `<URL>`
- GitHub mentions normalized to `<USER>`
- Non-ASCII ratio flagged (used for optional `--drop-mostly-non-ascii` filter)
- No section filtering, no title weighting

Applied via `preprocess_rows()` in all training scripts.

---

## 7. Dataset / Preprocessing Experiments — Rejected

All three alternatives failed to improve over the baseline. All data archived under `data/experiments/failed/`.

| Experiment | test_macro_f1 | vs baseline | Decision |
|---|---|---|---|
| Original (baseline) | 0.693839 | — | **OFFICIAL** |
| Support-only augmentation | 0.680766 | -0.013 | Rejected — val/test gap (0.840→0.681), weak question F1 (0.273) |
| Cleaned splits | 0.693839 | 0.000 | Rejected — no improvement |
| Strict text preprocessing | 0.637926 | -0.056 | Rejected — worst across all models |

Strict text used: title 2×, section filtering (drop OS/environment/runtime sections), URL→`<URL>`, image→`<IMAGE>`, mention→`<USER>`. Compression ~0.75 but hurt F1, likely by removing version/command context that matters for classification.

---

## 8. Classical ML Baseline

Script: `ml/classical/compare_classical.py`  
Artifacts: `artifacts/classical/best_model.joblib`, `reports/classical/`

| Model | val_macro_f1 | test_macro_f1 |
|---|---|---|
| LogisticRegression | 0.7019 | **0.6938** |
| LinearSVC | — | — |
| SGDClassifier | — | — |
| ComplementNB | — | — |
| MultinomialNB | — | — |
| DummyClassifier | — | — |

Best model: **LogisticRegression** (TF-IDF, ngram 1–2, max_features 50k, sublinear_tf).

Per-class test F1 (LogisticRegression):

| Class | Precision | Recall | F1 |
|---|---|---|---|
| bug | 0.608 | 0.844 | 0.707 |
| docs | 0.862 | 0.833 | 0.847 |
| feature | 0.835 | 0.900 | 0.866 |
| question | 0.490 | 0.278 | 0.355 |

`question` is the weakest class across all models — low recall.

---

## 9. Transformer Encoder Comparison

Script: `ml/finetune.py` (manual AdamW + DataLoader; no Trainer, no datasets, no pandas)  
All runs used: `data/processed/` official split, `model_text` input, lr=2e-5.

| run_name | model | epochs | batch | max_len | best_val_f1 | test_acc | test_macro_f1 | question_f1 |
|---|---|---|---|---|---|---|---|---|
| bert-tiny | prajjwal1/bert-tiny | 3 | 16 | 128 | 0.5622 | 0.5778 | 0.5634 | 0.3624 |
| electra_small_e5_len384 | google/electra-small-discriminator | 5 | 8 | 384 | 0.7040 | 0.7000 | 0.6909 | 0.3922 |
| **codebert_base_e3_len384** | **microsoft/codebert-base** | **3** | **4** | **384** | **0.6971** | **0.7500** | **0.7061** | 0.2909 |
| minilm_l12_e5_len384 | microsoft/MiniLM-L12-H384-uncased | 5 | 8 | 384 | 0.6289 | 0.6444 | 0.6332 | **0.4510** |

Notes:
- MiniLM has the best question F1 but is worst overall.
- CodeBERT has the weakest question recall (0.178) — the `question` class remains the hardest.
- ELECTRA-small is competitive but 0.015 below CodeBERT on test macro-F1.

Run artifacts: `artifacts/transformer/<run_name>/`  
Run reports: `reports/transformer/<run_name>/transformer_eval.json`  
Summary table: `reports/transformer/transformer_runs_summary.csv`

---

## 10. Final Transformer Choice

**microsoft/codebert-base**

Reason: highest test macro-F1 (0.7061) among all encoder experiments. Beats the classical baseline (+0.012). CodeBERT's pre-training on code-related corpora aligns with kubernetes issues that contain commands, YAML snippets, paths, version strings, and stack traces.

Artifact: `artifacts/transformer/codebert_base_e3_len384/`

---

## 11. Freeze Policy

**No frozen encoder layers. Full fine-tuning used.**

Defense:
- Training set has 1 680 balanced examples (420/class) — not extremely small.
- Kubernetes issues are domain-specific: commands, YAML, log lines, error traces, paths, version strings. Encoder adaptation to this vocabulary was desirable.
- CodeBERT showed no measured overfitting: `best_val_macro_f1=0.6971`, `test_macro_f1=0.7061`. Val and test are close; no val/test gap.
- Partial freezing was considered but not adopted because there was no overfitting signal requiring it. Adding a frozen-encoder ablation remains a future option.

---

## 12. Final Deployment Decision

| Attribute | Value |
|---|---|
| Model | microsoft/codebert-base |
| Artifact | `artifacts/transformer/codebert_base_e3_len384/` |
| Labels | bug / docs / feature / question |
| Input | `model_text` (title + body, URL/`<USER>` normalized) |
| Max length | 384 tokens |
| Inference | `AutoModelForSequenceClassification` via transformers |
| Serving | model_server container (no Torch in main app) |
| Operational fallback | LogisticRegression (TF-IDF) — `artifacts/classical/best_model.joblib` |

**Decision: FINAL.** CodeBERT has the best held-out test macro-F1 (0.7061) and accuracy (0.7500) across all three tracks. LogisticRegression is retained as operational fallback — only 0.012 lower macro-F1, no GPU required, ~110 000× faster per-sample inference.

---

## 13. Figures

Generated by `ml/make_classifier_figures.py`. Written to `reports/official/figures/`.

| Figure | Path | Description |
|---|---|---|
| 10 | `reports/official/figures/10_transformer_encoder_macro_f1.png` | All 4 encoder test macro-F1, classical baseline reference line |
| 11 | `reports/official/figures/11_transformer_question_f1.png` | All 4 encoder question class F1 (hardest class) |
| 12 | `reports/official/figures/12_classical_vs_transformer_macro_f1.png` | Classical vs CodeBERT macro-F1 and accuracy side-by-side |
| 13 | `reports/official/figures/13_codebert_per_class_f1.png` | Per-class F1: classical vs CodeBERT grouped bar chart |
| 14 | `reports/official/figures/14_classifier_decision_summary.png` | Decision summary table with deployment draft |

Earlier EDA and classical figures: `reports/official/figures/01–09_*.png`

---

## 14. LLM Baseline (Ollama local)

**Status: COMPLETE — llama3_full**

Script: `ml/llm_baseline.py`  
Prompt: `prompts/llm_baseline_classifier.md`  
Provider: Ollama local HTTP API (no API key, no Vault)  
Model: `llama3:latest`  
Run: `llama3_full` (360 test rows, zero-shot, temperature 0.0)

### Results

| Metric | Value |
|---|---|
| accuracy | 0.5850 |
| macro_f1 | **0.5554** |
| weighted_f1 | 0.5549 |
| valid_predictions | 359 / 360 |
| avg_latency | 24.9 s/sample |
| total_time | ~2.5 hours |
| cost | $0 |

Per-class F1:

| Class | Precision | Recall | F1 |
|---|---|---|---|
| bug | 0.432 | 0.956 | **0.595** |
| docs | 0.818 | 0.607 | 0.697 |
| feature | 0.760 | 0.633 | 0.691 |
| question | 0.684 | 0.144 | **0.239** |

Notes:
- `bug` has very high recall (0.956) but low precision — model over-predicts bug.
- `question` has the worst F1 (0.239), consistent with all three tracks.
- Zero-shot macro-F1 (0.555) is 0.139 below fine-tuned CodeBERT and 0.138 below classical baseline.

Artifacts: `reports/llm/llama3_full/`

```powershell
# Smoke run (10 rows)
uv run python ml/llm_baseline.py --limit 10

# Full run on official test split (360 rows)
uv run python ml/llm_baseline.py --run-name llama3_full

# Resume interrupted run
uv run python ml/llm_baseline.py --run-name llama3_full --resume
```

---

## 15. Three-Way Comparison

| Track | Model | test_macro_f1 | test_accuracy | question_f1 | deployment |
|---|---|---|---|---|---|
| Classical | LogisticRegression (TF-IDF) | 0.6938 | 0.7139 | 0.355 | fallback |
| **Transformer** | **microsoft/codebert-base** | **0.7061** | **0.7500** | 0.291 | **PRIMARY** |
| LLM zero-shot | llama3:latest (Ollama) | 0.5554 | 0.5850 | 0.239 | not selected |

Artifacts: `reports/classifier_three_way_comparison.json`, `reports/classifier_three_way_comparison.csv`  
Figures: `reports/official/figures/15–18_three_way_*.png`

Script: `ml/make_three_way_classifier_comparison.py`

---

## 16. Classification Golden Set

**Status: candidates generated, curation pending.**

A 25-issue hand-curated golden set for spot-checking and presentation demos.
Separate from the official test split (`data/processed/test.csv`).

| File | Status |
|---|---|
| `evals/golden/classification_golden_candidates.csv` | 48 candidates (12/class) — needs curation |
| `evals/golden/classification_golden.jsonl` | not yet created — final 25 after curation |
| `evals/golden/README.md` | curation instructions |

Script: `ml/create_classification_golden_candidates.py`

Candidate pool: sourced from `data/raw/kubernetes_issues.jsonl`, excluding all 2400 issue_numbers in the official splits.

| Class | Candidates available | Selected for review |
|---|---|---|
| bug | 797 | 12 |
| feature | 388 | 12 |
| docs | 306 | 12 |
| question | 19 | 12 |

**Next step:** open `evals/golden/classification_golden_candidates.csv`, fill `gold_label` for 25 issues, save as `classification_golden.jsonl`.

---

## 17. Tools API Architecture

Endpoint contracts defined. Both endpoints LIVE.

| Endpoint | Method | Status |
|---|---|---|
| `/api/v1/tools/entities` | POST | LIVE — deterministic rule-based NER, no model |
| `/api/v1/tools/summarize` | POST | LIVE — Ollama local LLM; 503 if unreachable |

**Layer map:**

```
app/api/schemas/tools.py          EntityExtract/Summarize Request+Response
app/api/routes/tools.py           HTTP-only router; maps domain errors → HTTP codes
app/services/tools/__init__.py    extract_entities_service, summarize_service (stub)
app/services/tools/entity_extractor.py  rule-based NER (existing)
app/infra/ollama_client.py        OllamaClient — async httpx scaffold for future summarize
app/domain/errors.py              ToolInputError, OllamaUnavailableError (new)
```

---

## 18. Remaining Tasks

- [x] Run Ollama LLM baseline — DONE (llama3_full, macro_f1=0.5554)
- [x] Three-way comparison table + figures (15-18) — DONE
- [x] Final deployment decision — DONE (CodeBERT primary, LogisticRegression fallback)
- [x] NER endpoint — LIVE at POST /api/v1/tools/entities
- [x] Tools API architecture — schemas, routes, infra scaffold in place
- [ ] Classification golden set — candidates generated; manually curate 25 into `classification_golden.jsonl`
- [x] Summarization endpoint — LIVE; Problem/Expected/Evidence/Component; 503 on Ollama unavailable
