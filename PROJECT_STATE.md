# Project State

## Project
Week 7 Maintainer's Copilot

## Deadline
Thursday night working demo, Friday 10-minute presentation.

## Current phase
Day 1 foundation finishing → next: label EDA before split/training.

## Chosen repo
kubernetes/kubernetes

## Current implementation status
- [x] Repo skeleton
- [x] Docker compose (all services healthy)
- [x] Vault dev service (SKIP_SETCAP fix, healthy)
- [x] API config loads secrets from Vault at boot
- [x] Tracing adapter (NoOpTracer with real IDs)
- [x] Structured logging with request_id and trace_id
- [x] Redaction before logs (GitHub tokens, JWTs, keys)
- [x] Alembic baseline migration (001)
- [x] GitHub token in Vault (secret/github, key: token) — confirmed working
- [x] Dataset validation script (scripts/validate_github_dataset.py, kubernetes defaults)
- [x] Label mapping documented (DECISIONS.md, kubernetes kind/* labels)
- [x] Dataset fetch script (ml/fetch_dataset.py, per-class Search API, dedup)
- [x] Label EDA script (ml/eda_labels.py)
- [x] Time-based stratified splits (ml/split_dataset.py, multi-label conflict reporting)
- [x] Fine-tuning stub (ml/finetune.py, smoke mode)
- [x] data/raw/kubernetes_issues.jsonl (real fetch completed — ~4k unique issues)
- [ ] reports/label_eda.json (EDA not yet run)
- [ ] reports/multilabel_conflicts.csv (split not yet run)
- [ ] data/processed/train|val|test.csv (split not yet run)
- [ ] artifacts/ (smoke run not yet run)

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
1. Run label EDA on Kubernetes issues (uv run python ml/eda_labels.py)
2. Review EDA output — confirm label mapping and conflict policy in DECISIONS.md
3. Generate splits, then smoke train (ml/split_dataset.py → ml/finetune.py --smoke)

## Commands
```bash
uv run pytest
docker compose up --build

# Dataset pipeline
uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000
uv run python ml/eda_labels.py
uv run python ml/split_dataset.py
uv run python ml/finetune.py --smoke
```
