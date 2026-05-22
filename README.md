# Handyman — Maintainer's Copilot

AI-powered copilot for Kubernetes issue triage. Classifies issues, answers questions via RAG, and stores maintainer preferences in memory.

## Quick start (local Docker)

```bash
cp .env.example .env
# Edit .env if you have a real Groq key (required for live chat):
#   secret/llm/groq_api_key must be set in Vault after startup
docker compose up --build
```

Startup order is automatic via `depends_on`:
1. `db`, `redis`, `minio`, `vault`, `jaeger` start
2. `vault-init` seeds local-dev secrets and exits
3. `migrate` runs `alembic upgrade head` and exits
4. `api`, `model_server` start
5. `chatbot` starts after `api` is healthy

## Services and ports

| Service | URL | Purpose |
|---|---|---|
| API | http://localhost:8000 | FastAPI — auth, chat, RAG, memory, widget |
| API docs | http://localhost:8000/docs | Interactive OpenAPI UI |
| Model server | http://localhost:8001 | LR TF-IDF classifier (no GPU) |
| Chatbot | http://localhost:8501 | Streamlit authenticated UI |
| Widget | http://localhost:3000 | Nginx serving the React widget bundle |
| Host demo | http://localhost:8080 | Demo host page with embedded widget |
| MinIO | http://localhost:9001 | Blob storage console |
| Vault | http://localhost:8200 | Secrets (local dev mode) |
| Jaeger | http://localhost:16686 | Distributed traces UI |

## Widget URL flow

```
Host page (localhost:8080)
  └─ loads /widget.js from API (localhost:8000/widget.js)
       └─ creates <iframe> pointing to widget service (localhost:3000)
            └─ widget React app calls API at localhost:8000/api/v1/chat
```

For `docker compose` deployments the iframe URL is `http://localhost:3000`.
For local dev (without Docker) the iframe URL is `http://localhost:5173` (Vite dev server)
or `http://localhost:8000/widget-app/` if `widget/dist/` has been built.

## Groq API key (for live chat)

Chat requires a real Groq API key in Vault:

```bash
# After docker compose up (vault-init runs first):
docker compose exec vault vault kv put secret/llm groq_api_key="gsk_your_real_key"
```

Without this key, `/api/v1/chat` returns `GroqUnavailableError`. All other features work without it.

## Run tests (no Docker required)

```bash
uv run pytest
```

## Production deployment notes

See `RUNBOOK.md` — "Production deployment" section for Vault provisioning requirements.
Production mode refuses `dev-root-token` and placeholder `jwt_signing_key` at startup.

## Key documents

| Document | Purpose |
|---|---|
| `RUNBOOK.md` | Local and production deployment |
| `DECISIONS.md` | Locked technical decisions with numbers |
| `EVALS.md` | CI eval gates and thresholds |
| `SECURITY.md` | Secret management and redaction policy |
| `docs/PROJECT_BRIEF_CANONICAL.md` | Implementation contract |
