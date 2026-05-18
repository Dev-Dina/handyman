# Runbook

## First setup

```bash
cp .env.example .env
docker compose up --build
```

## Day-to-day

```bash
# Run tests
uv run pytest

# Rebuild a single service
docker compose up --build api

# Apply migrations
docker compose run --rm migrate
```

## Vault (local dev)

```bash
# Vault starts in dev mode via docker compose
# Root token is in .env as VAULT_DEV_ROOT_TOKEN
# UI available at http://localhost:8200
```

## Useful checks

```bash
# Confirm all containers healthy
docker compose ps

# Tail api logs
docker compose logs -f api

# Tail model_server logs
docker compose logs -f model_server
```
