# Project State

## Project
Week 7 Maintainer's Copilot

## Deadline
Thursday night working demo, Friday 10-minute presentation.

## Current phase
Phase 1 — DL/NLP track

## Chosen repo
kubernetes/kubernetes

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
- [ ] reports/text_quality_report.json
- [ ] Classical ML baseline
- [ ] Real transformer training + evaluation
- [ ] LLM baseline

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
None.

## Next 3 tasks
1. Run text quality report (uv run python ml/text_preprocessing.py)
2. Build classical ML baseline on same splits
3. Run real transformer evaluation + model card

## Commands
```bash
uv run pytest
docker compose up --build

# Dataset pipeline
uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000
uv run python ml/eda_labels.py
uv run python ml/split_dataset.py --max-per-class 600
uv run python ml/text_preprocessing.py
uv run python ml/finetune.py --smoke
uv run python ml/finetune.py
```
