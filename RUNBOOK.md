# Runbook

## First setup

```bash
cp .env.example .env
# Edit .env to set real LLM/tracing keys if needed, then:
docker compose up --build
```

Startup order (automatic via depends_on):
1. db, redis, minio, vault start
2. vault-init seeds secrets into Vault and exits
3. migrate runs `alembic upgrade head` and exits
4. api, model_server start
5. chatbot starts after api is healthy

## Day-to-day

```bash
# Run tests
uv run pytest

# Rebuild a single service
docker compose up --build api

# Apply migrations
docker compose run --rm migrate

# Tail all logs
docker compose logs -f

# Stop everything
docker compose down

# Stop and wipe volumes
docker compose down -v
```

## Vault (local dev)

Vault runs in dev mode. Root token default: `dev-root-token`. UI: http://localhost:8200

### Store GitHub token in Vault (PowerShell)

> **NEVER paste the GitHub token into chat, code, .env, or commits.**

```powershell
# 1. Start Vault
docker compose up -d vault

# 2. Capture token in a shell variable (not in history/files)
$env:GITHUB_TOKEN = Read-Host "Paste GitHub token"

# 3. Write token into Vault
docker compose exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=dev-root-token vault vault kv put secret/github token="$env:GITHUB_TOKEN"

# 4. Clear variable from session
Remove-Item Env:\GITHUB_TOKEN
```

## Migrations

```bash
# Run baseline migration against local DB
DATABASE_URL=postgresql+asyncpg://handyman:password@localhost:5432/handyman \
  uv run alembic upgrade head

# Generate a new migration after ORM model changes
DATABASE_URL=postgresql+asyncpg://handyman:password@localhost:5432/handyman \
  uv run alembic revision --autogenerate -m "describe change"

# Rollback one revision
DATABASE_URL=postgresql+asyncpg://handyman:password@localhost:5432/handyman \
  uv run alembic downgrade -1
```

The `migrate` docker-compose service runs `alembic upgrade head` with `DATABASE_URL` injected.

## Dataset pipeline (kubernetes/kubernetes)

Requires GitHub token in Vault (see above). Run in order.

```powershell
# 1. Validate dataset viability (sample 300 issues, writes reports/dataset_validation_kubernetes.json)
uv run python scripts/validate_github_dataset.py --repo kubernetes/kubernetes --sample-size 300

# 2. Fetch per-class dataset (writes data/raw/kubernetes_issues.jsonl)
#    Fetches up to 1000 issues per target label via Search API (~100 s with token)
uv run python ml/fetch_dataset.py --repo kubernetes/kubernetes --per-class 1000

# 3. Run label EDA (writes reports/label_eda.json + CSV reports)
uv run python ml/eda_labels.py

# 4. Build train/val/test splits (writes data/processed/train|val|test.csv + labeled_issues.csv)
#    Also writes reports/multilabel_conflicts.csv and reports/split_report.json
uv run python ml/split_dataset.py

# 5. Smoke-test fine-tuning (prajjwal1/bert-tiny, 2 steps, CPU, writes artifacts/smoke/)
uv run python ml/finetune.py --smoke

# 6. Full fine-tuning (distilbert-base-uncased, 3 epochs, writes artifacts/full/)
uv run python ml/finetune.py
```

ML extras required for finetune:
```bash
uv sync --extra ml
```

Vault token path for GitHub:
- Address:  VAULT_ADDR=http://127.0.0.1:8200
- Token:    VAULT_TOKEN=dev-root-token
- Path:     secret/github
- Key:      token

## Useful checks

```bash
# Confirm all containers healthy
docker compose ps

# Tail api logs
docker compose logs -f api

# Tail model_server logs
docker compose logs -f model_server
```
