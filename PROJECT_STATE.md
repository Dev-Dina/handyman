# Project State

## Project
Week 7 Maintainer's Copilot

## Deadline
Thursday night working demo, Friday 10-minute presentation.

## Current phase
MON Foundations:
- Repo skeleton
- Docker compose with all services
- Vault wired
- Tracing wired from day one
- Alembic baseline
- Dataset fetch
- Splits
- Start fine-tuning

## Chosen repo
TODO

## Current implementation status
- [x] Repo skeleton
- [ ] Docker compose
- [ ] Vault dev service
- [x] API config loads secrets from Vault
- [x] Tracing adapter
- [x] Structured logging with request_id and trace_id
- [ ] Alembic baseline
- [ ] Dataset fetch script
- [ ] Label mapping
- [ ] Time-based stratified splits
- [ ] Fine-tuning script stub

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
1. Create repo skeleton
2. Add docker-compose services
3. Add dataset fetch/split scripts

## Commands
```bash
uv run pytest
docker compose up --build
```
