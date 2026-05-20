# Project State

## Project
Week 7 Maintainer's Copilot

## Deadline
Thursday night working demo, Friday 10-minute presentation.

## Current phase
Phase 1 - DL/NLP track

## Chosen repo
kubernetes/kubernetes

---

## Current official classifier status

| Track | Model | test_macro_f1 | test_accuracy | Status |
|---|---|---|---|---|
| Classical baseline | LogisticRegression (TF-IDF) | 0.6938 | 0.7139 | LOCKED — fallback |
| Best transformer | microsoft/codebert-base | 0.7061 | 0.7500 | LOCKED — PRIMARY |
| LLM baseline | llama3:latest (Ollama) | 0.5554 | 0.5850 | LOCKED |

**Final deployment decision: CodeBERT primary, LogisticRegression operational fallback.**

Official data: `data/processed/` — LOCKED (1680 train / 360 val / 360 test, 420/90/90 per class)

Failed experiments archived: `data/experiments/failed/` + `reports/experiments/failed/`

---

## Where to find things

| What | Path |
|---|---|
| Official figures (presentation) | `reports/official/figures/` (01-14) |
| EDA + classical reports | `reports/classical/`, `reports/kubernetes_*.json/csv` |
| Transformer run reports | `reports/transformer/` (per-run subdirs) |
| Transformer runs summary | `reports/transformer/transformer_runs_summary.csv` |
| LLM baseline reports | `reports/llm/` (per-run subdirs) |
| LLM runs summary | `reports/llm/llm_runs_summary.csv` |
| Failed experiment reports | `reports/experiments/failed/` |
| Raw dataset | `data/raw/kubernetes_issues.jsonl` |
| Official splits | `data/processed/train.csv`, `val.csv`, `test.csv` |
| Classical model artifact | `artifacts/classical/best_model.joblib` |
| Transformer model artifacts | `artifacts/transformer/<run_name>/` |
| Living classifier report | `docs/CLASSIFIER_TRACK_REPORT.md` |
| Full path manifest | `reports/artifact_manifest.json` |

---

## Phase 0 — Foundation (VERIFIED COMPLETE)

| Check | Status |
|---|---|
| docker compose config valid | PASS |
| Vault healthy | PASS |
| secret/github in Vault | PASS |
| secret/handyman in Vault (vault-init) | PASS |
| API imports locally (Maintainer's Copilot API) | PASS |
| db healthy | PASS |
| Alembic baseline migration (001), exit 0 | PASS |
| Redaction tests | 5/5 PASS |
| Full pytest suite | PASS |
| data/raw/kubernetes_issues.jsonl | EXISTS |
| data/raw/numpy_issues.jsonl | ARCHIVED → data/archive_numpy/ |
| data/processed/train.csv | EXISTS (1680 rows, 420/class) |
| data/processed/val.csv | EXISTS (360 rows, 90/class) |
| data/processed/test.csv | EXISTS (360 rows, 90/class) |
| Split cap: 600/class, 70/15/15, per-class chronological | DONE |
| Global chronological limitation | DOCUMENTED in DECISIONS.md |
| Smoke fine-tune (bert-tiny, 2 steps, CPU) | PASS |
| artifacts/smoke/model_card.json | EXISTS |
| artifacts/smoke/model/model.safetensors | EXISTS |
| artifacts/smoke/model/tokenizer.json | EXISTS |
| ml/text_preprocessing.py (model_text, non-ASCII flags) | EXISTS |

## Current implementation status

### Infrastructure
- [x] Repo skeleton
- [x] Docker compose (all services healthy, config validated)
- [x] Vault dev service (SKIP_SETCAP fix, healthy)
- [x] API config loads secrets from Vault at boot
- [x] Tracing adapter (NoOpTracer with real IDs)
- [x] Structured logging with request_id and trace_id
- [x] Redaction before logs (GitHub tokens, JWTs, keys) — 5 tests pass
- [x] Alembic baseline migration (001)
- [x] GitHub token in Vault (secret/github, key: token)
- [x] App secrets in Vault (secret/handyman, seeded by vault-init)

### Dataset pipeline
- [x] Dataset validation script (scripts/validate_github_dataset.py)
- [x] Label mapping documented (DECISIONS.md, kubernetes kind/* labels)
- [x] Dataset fetch script (ml/fetch_dataset.py, per-class Search API, dedup, --supplement-label)
- [x] data/raw/kubernetes_issues.jsonl (3923 unique issues)
- [x] Label EDA script (ml/eda_labels.py, kubernetes_* prefixed outputs)
- [x] reports/kubernetes_label_eda.json (proceed_to_split=True)
- [x] reports/kubernetes_multilabel_conflicts.csv (536 conflicts)
- [x] reports/kubernetes_class_balance_before_split.csv
- [x] reports/archive_numpy/ (old numpy reports archived)

### Splits
- [x] ml/split_dataset.py (--max-per-class, per-class chronological, conflict reporting)
- [x] data/processed/train.csv — 1680 rows, 420/class
- [x] data/processed/val.csv — 360 rows, 90/class
- [x] data/processed/test.csv — 360 rows, 90/class

### ML
- [x] ml/text_preprocessing.py (model_text, URL/<USER> normalisation, non-ASCII flags, --drop-mostly-non-ascii)
- [x] ml/finetune.py (smoke mode, model_text wired, --drop-mostly-non-ascii flag)
- [x] artifacts/smoke/ (bert-tiny, 2 steps, CPU, model card + safetensors + tokenizer)
- [x] reports/text_quality_report.json
- [x] ml/make_eda_figures.py (6 PNG figures in reports/figures/)
- [x] Classical ML baseline (TF-IDF + LogisticRegression, accuracy 0.713889, macro_f1 0.693839)
- [x] Classical model comparison (6 models, best=LogisticRegression, val_macro_f1 0.701875, test_macro_f1 0.693839)
- [x] Support-only augmentation experiment (ABLATION — not adopted; test_macro_f1 0.680766 < baseline 0.693839, question F1 0.272727; archived to data/experiments/failed/)
- [x] Cleaned splits experiment (ABLATION — no gain, 0.693839 = baseline; archived to data/experiments/failed/)
- [x] Strict text preprocessing experiment (ABLATION — worst, 0.637926; archived to data/experiments/failed/)
- [x] ml/finetune.py - manual PyTorch loop (AdamW + DataLoader); no Trainer/TrainingArguments/datasets/pandas/numpy; saves best by val macro-F1; --run-name/--reports-dir per-run isolation; writes reports/transformer/<run_name>/transformer_{eval,training_history}.json + artifacts/transformer/<run_name>/; appends reports/transformer/transformer_runs_summary.csv
- [x] Create .venv-gpu (CUDA, local), torch.cuda.is_available()=True, CUDA GPU verified
- [x] Transformer encoder comparison: bert-tiny/electra-small/codebert-base/minilm-l12 — COMPLETE; best=microsoft/codebert-base test_macro_f1=0.7061
- [x] docs/CLASSIFIER_TRACK_REPORT.md — living classifier report created
- [x] ml/make_classifier_figures.py — 5 classifier figures (10-14) in reports/official/figures/
- [x] ml/classifier_config.py — centralized constants (LABELS, paths, known metrics, Ollama defaults); used by finetune.py, llm_baseline.py, make_classifier_figures.py, compare_classical.py
- [x] LLM baseline run — llama3_full COMPLETE; macro_f1=0.5554, accuracy=0.5850; reports/llm/llama3_full/
- [x] Three-way comparison — reports/classifier_three_way_comparison.json/csv + figures 15-18
- [x] Final deployment decision — CodeBERT primary, LogisticRegression fallback
- [x] Classification golden set candidates — evals/golden/classification_golden_candidates.csv (48 rows, 12/class; pending manual curation)
- [x] Tools API architecture — schemas, routes, infra scaffold (app/api/schemas/, app/api/routes/, app/infra/ollama_client.py)
- [x] NER endpoint — POST /api/v1/tools/entities LIVE; calls extract_entities_service
- [x] Summarization endpoint — POST /api/v1/tools/summarize LIVE; Problem/Expected/Evidence/Component prompt via OllamaClient; 503 on unavailable

### Official classifier dataset

```
data/processed/train.csv — 1680 rows, 420/class  (LOCKED)
data/processed/val.csv   — 360 rows, 90/class    (LOCKED)
data/processed/test.csv  — 360 rows, 90/class    (LOCKED)
```

Failed experiment data (archived — do not use as training inputs):

```
data/experiments/failed/support_augmented/   augmentation — rejected, F1 0.681
data/experiments/failed/cleaned_splits/      cleaned splits — no gain, F1 0.694
data/experiments/failed/strict_text/         strict preprocessing — rejected, F1 0.638
```

### Env separation
- Main env (.venv via uv): no Torch, no accelerate. Runs app, tests, classical ML.
- GPU env (.venv-gpu, local only): Torch CUDA, transformers, accelerate. Runs finetune.py.
- Docker: no Torch. Never install Torch in Dockerfiles.

## Architecture rules
- app/api = HTTP only
- app/services = business logic
- app/repositories = SQL only
- app/domain = domain models/errors
- app/infra = external adapters
- No SQLAlchemy in routers
- No HTTPException in services/repositories
- Secrets from Vault, not .env except Vault token/ports
- Redaction before logs/traces/memory

## Current blockers
none

## Next 3 tasks
1. Manually curate evals/golden/classification_golden_candidates.csv into evals/golden/classification_golden.jsonl (25 issues, fill gold_label)
2. Manually curate evals/golden/classification_golden_candidates.csv into classification_golden.jsonl
3. Smoke test tools API endpoints against running docker compose stack

## Commands
```bash
uv run pytest
docker compose up --build

# Dataset pipeline
uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000
uv run python ml/eda_labels.py
uv run python ml/split_dataset.py --max-per-class 600
uv run python ml/text_preprocessing.py
uv run python ml/classical_baseline.py
uv run python ml/classical/compare_classical.py
```

```powershell
# Transformer fine-tuning (GPU env — not uv)
.\.venv-gpu\Scripts\python.exe ml\finetune.py --smoke
.\.venv-gpu\Scripts\python.exe ml\finetune.py --model microsoft/codebert-base --run-name codebert_base_e3_len384 --epochs 3 --batch-size 4 --max-len 384
```
