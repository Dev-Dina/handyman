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
