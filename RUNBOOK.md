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

```bash
# Vault starts in dev mode via docker compose
# Root token is in .env as VAULT_DEV_ROOT_TOKEN
# UI available at http://localhost:8200
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

## Useful checks

```bash
# Confirm all containers healthy
docker compose ps

# Tail api logs
docker compose logs -f api

# Tail model_server logs
docker compose logs -f model_server
```
