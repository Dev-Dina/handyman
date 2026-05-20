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

## Temporary active-run note

While llama3_full is running, do not move/delete `reports/llm/llama3_full/` or edit cached prediction files (`llm_raw_responses.jsonl`). Resume is safe once the run completes.

---

## Current official classifier status

| Track | Model | test_macro_f1 | test_accuracy | Status |
|---|---|---|---|---|
| Classical baseline | LogisticRegression (TF-IDF) | 0.6938 | 0.7139 | LOCKED — official |
| Best transformer | microsoft/codebert-base | 0.7061 | 0.7500 | LOCKED — best encoder |
| LLM baseline | llama3:latest (Ollama) | pending | pending | run in progress |

Deployment draft: CodeBERT (best F1). Final decision after LLM result.

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

## Phase 0 â€” Foundation (VERIFIED COMPLETE)

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
| data/raw/numpy_issues.jsonl | ARCHIVED â†’ data/archive_numpy/ |
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
- [x] Redaction before logs (GitHub tokens, JWTs, keys) â€” 5 tests pass
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
- [x] data/processed/train.csv â€” 1680 rows, 420/class
- [x] data/processed/val.csv â€” 360 rows, 90/class
- [x] data/processed/test.csv â€” 360 rows, 90/class

### ML
- [x] ml/text_preprocessing.py (model_text, URL/<USER> normalisation, non-ASCII flags, --drop-mostly-non-ascii)
- [x] ml/finetune.py (smoke mode, model_text wired, --drop-mostly-non-ascii flag)
- [x] artifacts/smoke/ (bert-tiny, 2 steps, CPU, model card + safetensors + tokenizer)
- [x] reports/text_quality_report.json
- [x] ml/make_eda_figures.py (6 PNG figures in reports/figures/)
- [x] Classical ML baseline (TF-IDF + LogisticRegression, accuracy 0.713889, macro_f1 0.693839)
- [x] Classical model comparison (6 models, best=LogisticRegression, val_macro_f1 0.701875, test_macro_f1 0.693839)
- [x] Support-only augmentation experiment (ABLATION â€” not adopted; augmented test_macro_f1 0.680766 < original 0.693839, question F1 0.272727)
- [x] Clean single-target count script (augmented raw data: bug 956, feature 963, docs 849, question 1000; 600/class possible)
- [x] Cleaned processed splits materialized (raw data/processed/ preserved; data/processed_cleaned/ created with model_text + quality flags)
- [x] ml/finetune.py - manual PyTorch loop (AdamW + DataLoader); no Trainer/TrainingArguments/datasets/pandas/numpy; saves best by val macro-F1; --run-name/--reports-dir per-run isolation; writes reports/transformer/<run_name>/transformer_{eval,training_history}.json + artifacts/transformer/<run_name>/; appends reports/transformer/transformer_runs_summary.csv
- [x] Create .venv-gpu (CUDA, local), torch.cuda.is_available()=True, CUDA GPU verified
- [x] Transformer encoder comparison: bert-tiny/electra-small/codebert-base/minilm-l12 -- COMPLETE; best=microsoft/codebert-base test_macro_f1=0.7061
- [x] docs/CLASSIFIER_TRACK_REPORT.md -- living classifier report created
- [x] ml/make_classifier_figures.py -- 5 classifier figures (10-14) in reports/official/figures/
- [x] ml/classifier_config.py -- centralized constants (LABELS, paths, known metrics, Ollama defaults); used by finetune.py, llm_baseline.py, make_classifier_figures.py, compare_classical.py
- [ ] LLM baseline run -- ml/llm_baseline.py ready, run IN PROGRESS (llama3_full, reports/llm/llama3_full/)

### Official classifier dataset
data/processed/train.csv â€” 1680 rows, 420/class
data/processed/val.csv â€” 360 rows, 90/class
data/processed/test.csv â€” 360 rows, 90/class
data/processed_cleaned/train.csv â€” cleaned model_text + quality flags, originals preserved
data/processed_cleaned/val.csv â€” cleaned model_text + quality flags, originals preserved
data/processed_cleaned/test.csv â€” cleaned model_text + quality flags, originals preserved
Augmented splits (data/processed_augmented/) are experiment artifacts only.

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
LLM baseline (llama3_full) running — do not interrupt reports/llm/ or related files.

## Next 3 tasks
1. Wait for llama3_full result in reports/llm/llama3_full/llm_eval.json; record macro_f1
2. Generate three-way comparison table + figures (classical / CodeBERT / LLM)
3. Create 25-example classification golden set + wire NER endpoint

## Commands
```bash
uv run pytest
docker compose up --build

# Dataset pipeline
uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000
uv run python ml/eda_labels.py
uv run python ml/split_dataset.py --max-per-class 600
uv run python ml/text_preprocessing.py
.\.venv\Scripts\python.exe ml\clean_processed_splits.py
uv run python ml/classical_baseline.py
uv run python ml/classical/compare_classical.py
uv run python ml/finetune.py --smoke
uv run python ml/finetune.py
```
