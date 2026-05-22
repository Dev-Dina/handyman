# Runbook

## Canonical project contract

Three documents govern what must be built and in what order:

| Document | Purpose |
|---|---|
| `docs/PROJECT_BRIEF_CANONICAL.md` | Authority — non-negotiable architecture, locked decisions, required remaining work |
| `docs/PROJECT_BRIEF_VALIDATION.md` | Compliance table — brief requirement vs. evidence vs. status |
| `PROJECT_STATE.md` | Living state — current implementation status, blockers, next tasks |

Future implementation must follow `docs/PROJECT_BRIEF_CANONICAL.md`.

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

## Testing

```powershell
# Full suite (safe: no Docker, no Ollama, no network)
.\.venv\Scripts\python.exe -m pytest -q

# Dry run (collect only)
.\.venv\Scripts\python.exe -m pytest --collect-only

# By category
.\.venv\Scripts\python.exe -m pytest tests/unit        # 191 pure-function tests
.\.venv\Scripts\python.exe -m pytest tests/smoke       # 11 import/route sanity checks
.\.venv\Scripts\python.exe -m pytest tests/integration # 65 FastAPI endpoint tests (mocked)
.\.venv\Scripts\python.exe -m pytest tests/eval        # 24 golden/schema/threshold gates
.\.venv\Scripts\python.exe -m pytest tests/build       # 2 compose/config structural checks

# By marker
.\.venv\Scripts\python.exe -m pytest -m unit
.\.venv\Scripts\python.exe -m pytest -m "not build"
```

See `tests/README.md` for category definitions and rules.

## CI / eval gates

GitHub CI splits checks into independent jobs so each failure points to the exact layer.
Never uses `--all-extras`, Docker runtime, `.venv-gpu`, Groq, Ollama, or live MinIO.

Local equivalents for each CI job:

```powershell
# ci-assets — check gitignored assets exist before eval jobs run
python scripts/check_ci_assets.py

# lint — ruff on all source directories (includes scripts + notebooks)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests chatbot scripts notebooks

# tests-unit
.\.venv\Scripts\python.exe -m pytest -m unit -q

# tests-smoke
.\.venv\Scripts\python.exe -m pytest -m smoke -q

# tests-integration
.\.venv\Scripts\python.exe -m pytest -m integration -q

# tests-eval (golden schema + threshold gate tests)
.\.venv\Scripts\python.exe -m pytest -m eval -q

# tests-build (docker compose structural checks — no Docker execution)
.\.venv\Scripts\python.exe -m pytest tests/build -q

# classifier-golden-eval (requires artifacts/classical/best_model.joblib)
.\.venv\Scripts\python.exe -m pipelines.classifier.eval_golden

# rag-golden-eval (requires data/rag/chunks/chunks_section_aware.jsonl)
.\.venv\Scripts\python.exe -m pipelines.rag.eval_api

# widget-build (requires Node 20)
cd widget && npm ci && npm run build && cd ..

# docker-compose-config (config validation only — does not start services)
docker compose config
```

Outputs:
- `reports/classification_eval_report.json`
- `reports/rag/api_eval_report.json`
- `widget/dist/` (from widget-build)

## Reports audit and review notebooks

```powershell
# Regenerate the reports inventory.
.\.venv\Scripts\python.exe scripts/audit_reports.py

# Review the reports map.
.\.venv\Scripts\python.exe -m marimo run notebooks/00_reports_map.py

# Review classifier experiment decisions.
.\.venv\Scripts\python.exe -m marimo run notebooks/01_classifier_experiments_review.py

# Review RAG retrieval decisions.
.\.venv\Scripts\python.exe -m marimo run notebooks/02_rag_retrieval_review.py
```

The notebooks read existing reports only. They do not retrain, fetch data, call
external services, or mutate source artifacts.

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

## Widget (WIDGET-2)

### Build and run

The embeddable React widget lives in `widget/`. The backend serves the built files.

```powershell
# One-time dependency install (run after cloning or after package.json changes)
cd widget
npm install

# Production build — outputs to widget/dist/
# FastAPI auto-serves dist/ at /widget-app/ once the directory exists
npm run build
cd ..

# Security note: npm audit reports 2 moderate vulnerabilities (esbuild/vite dev server,
# GHSA-67mh-4wv8-2f99). Both are dev-server only — production bundle is unaffected.
# Do NOT run npm audit fix --force without review; it installs vite@8 (breaking change).

# Widget dev server (hot-reload at http://localhost:5173/widget-app/)
# Use data-widget-url="http://localhost:5173/widget-app/" in the loader script
# to point the iframe at the dev server during development
cd widget
npm run dev
```

### Open the host demo

```powershell
# 1. Start the backend
docker compose up -d

# 2. Build the widget (see above)

# 3. Create a widget config and note the public_widget_id UUID
#    (via Streamlit admin page or POST /api/v1/admin/widgets)

# 4. Edit demo/host/index.html — replace YOUR-PUBLIC-WIDGET-ID with the real UUID

# 5. Open in a browser directly (no extra server needed)
#    Windows: start demo\host\index.html
#    Or drag the file into a browser tab
```

### Embed snippet

```html
<script
  src="http://localhost:8000/widget.js"
  data-widget-id="YOUR-PUBLIC-WIDGET-ID"
  data-api-base-url="http://localhost:8000"
></script>
```

### Architecture

```
GET /widget.js          → app/api/routes/widget_loader.py
                           → app/services/widgets/loader.py (JavaScript string)
GET /widget-app/*       → FastAPI StaticFiles mount on widget/dist/ (requires npm run build)
GET /api/v1/widgets/:id → widget fetches config (theme, greeting, enabled_tools)
POST /api/v1/chat       → widget sends chat messages
```

## Streamlit internal app (STREAMLIT-1)

The Streamlit app is the authenticated internal interface for demos and operational review.

### Start the app

```powershell
# 1. Start the full backend stack (API + DB + Redis + Vault + Jaeger)
docker compose up -d

# 2. Start the Streamlit app (separate process, not in Docker by default)
.\.venv\Scripts\python.exe -m streamlit run chatbot/main.py

# Or with a custom API URL
$env:API_BASE_URL = "http://localhost:8000"
.\.venv\Scripts\python.exe -m streamlit run chatbot/main.py
```

App runs at: http://localhost:8501

### Manual smoke test

```
1. Register a user:
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"demo@example.com","password":"password123"}'

2. Open http://localhost:8501 — sign in with the registered email/password.

3. Type a chat message (e.g. "What is a Kubernetes pod?"). Verify:
   - Answer appears below the input.
   - Conversation ID is shown at the top.
   - Tool calls expander appears if tools were used.

4. Click "Memory Inspector" in the sidebar.
   - Short-term and long-term memory panels appear.
   - If no write_memory tool has been called, panels show "no items" message.

5. Click "Widget Admin" — non-admin sees access-denied message.
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

Migration chain: 001 (baseline) → 002 (chat1 schema) → 003 (memory2 long-term) → 004 (pgvector embedding).

## MinIO (blob storage)

MinIO starts automatically with `docker compose up`. Console: http://localhost:9001

Credentials come from Vault (`secret/handyman` → `minio_access_key` / `minio_secret_key`).
Endpoint: env var `MINIO_ENDPOINT` (default `localhost:9000`; Docker: `minio:9000`).

**Do not hardcode MinIO credentials.** Never print `access_key` or `secret_key`.

### Upload artifacts and eval reports

```powershell
# Upload key reports (artifact_manifest.json, eval reports, eval_thresholds.yaml)
.\.venv\Scripts\python.exe -m pipelines.blob.upload_artifacts

# Dry run — list files without uploading
.\.venv\Scripts\python.exe -m pipelines.blob.upload_artifacts --dry-run

# Also upload model artifact files (large — explicit opt-in)
.\.venv\Scripts\python.exe -m pipelines.blob.upload_artifacts --include-model-artifacts
```

Upload summary is written to `reports/blob/upload_summary.json` after every run.
Check `status` field per file: `uploaded`, `skipped` (not_found), or `failed`.

Migration 004 requires the Postgres image to have the pgvector extension installed.
The docker-compose `db` service uses `pgvector/pgvector:pg16` which provides it.
Running migration 004 against a vanilla Postgres image will fail.

## Dataset pipeline (kubernetes/kubernetes)

Requires GitHub token in Vault (see above). Run in order.

Vault env for local dev (already in .env):
```
VAULT_ADDR=http://127.0.0.1:8200
VAULT_DEV_ROOT_TOKEN=dev-root-token
```
GitHub token path in Vault: `secret/github`, key: `token`

```powershell
# 1. Validate dataset viability (sample 300 issues)
#    Writes reports/dataset_validation_kubernetes.json
uv run python scripts/validate_github_dataset.py --repo kubernetes/kubernetes --sample-size 300

# 2. Fetch per-class dataset (~100 s with token)
#    Writes data/raw/kubernetes_issues.jsonl
uv run python -m ml.fetch_dataset --repo kubernetes/kubernetes --per-class 1000

#    Optional: supplement question class if EDA shows imbalance (run after step 3)
uv run python -m ml.fetch_dataset --repo kubernetes/kubernetes --per-class 1000 --supplement-label "kind/support" --supplement-count 1000

# 3. Run label EDA — review before splitting
#    Writes reports/kubernetes_label_eda.json + kubernetes_*.csv reports
uv run python -m ml.eda_labels

# 4. Build train/val/test splits
#    Writes data/processed/train|val|test.csv + labeled_issues.csv
#    Also writes reports/kubernetes_multilabel_conflicts.csv and reports/split_report.json
uv run python -m ml.split_dataset

# 5. Train classical TF-IDF + LogisticRegression baseline
#    Writes artifacts/classical/ and reports/classical_*
uv run python -m ml.classical_baseline

# 6. Compare classical TF-IDF models
#    Writes reports/classical/, reports/figures/08-09_*.png, and artifacts/classical/best_model.*
uv run python -m ml.classical.compare_classical

# 7. Smoke-test fine-tuning (prajjwal1/bert-tiny, 2 steps, CPU)
#    Writes artifacts/transformer/smoke/
.\.venv-gpu\Scripts\python.exe -m ml.finetune --smoke

# 8. Full fine-tuning with run name (e.g. codebert)
#    Writes artifacts/transformer/<run_name>/ + reports/transformer/<run_name>/
.\.venv-gpu\Scripts\python.exe -m ml.finetune --model microsoft/codebert-base --run-name codebert_base_e3_len384 --epochs 3 --batch-size 4 --max-len 384

# 9. LLM zero-shot baseline (Ollama, no GPU)
#    Writes reports/llm/<run_name>/
uv run python -m ml.llm_baseline --run-name llama3_full

# 10. Generate classifier presentation figures (10-14)
#     Writes reports/official/figures/10-14_*.png
uv run python -m ml.make_classifier_figures

# 11. Generate three-way comparison figures and artifacts (after LLM baseline)
#     Writes reports/classifier_three_way_comparison.json/csv
#     Writes reports/official/figures/15-18_*.png
uv run python -m ml.make_three_way_classifier_comparison
```

ML extras required for classical baseline (no Torch):
```bash
uv sync --extra ml
```

## GPU training environment (local only — NOT Docker)

> **Policy:**
> - Main project env (`.venv`) and Docker builds contain **no Torch**.
> - Do not run `uv sync --all-extras` — it will attempt to download `torch` (2.6 GB).
> - Do not let agents run `uv sync`, `pip install`, or any package install commands.
> - Transformer fine-tuning runs exclusively from `.venv-gpu` (CUDA, Windows-local).
> - Docker builds never install Torch; all production inference uses the API or model_server.

### Create `.venv-gpu` (one-time, Windows PowerShell with CUDA GPU)

```powershell
py -3.12 -m venv .venv-gpu
.\.venv-gpu\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install transformers datasets accelerate scikit-learn pandas numpy joblib matplotlib
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

### Run transformer fine-tuning from `.venv-gpu`

```powershell
# Smoke test
.\.venv-gpu\Scripts\python.exe -m ml.finetune --smoke

# Full run with explicit run name (example: codebert-base, 3 epochs)
.\.venv-gpu\Scripts\python.exe -m ml.finetune --model microsoft/codebert-base --run-name codebert_base_e3_len384 --epochs 3 --batch-size 4 --max-len 384
```

Vault token path for GitHub:
- Address:  VAULT_ADDR=http://127.0.0.1:8200
- Token:    VAULT_TOKEN=dev-root-token
- Path:     secret/github
- Key:      token

## LLM baseline (Ollama local)

> **Do not interrupt if a run is active — check `reports/llm/` first.**

Requires Ollama running locally with `llama3:latest` pulled. No API key. No Vault.

```powershell
# Start Ollama (separate terminal, leave running)
ollama serve

# Pull model (one-time)
ollama pull llama3:latest

# Smoke run (10 rows)
uv run python -m ml.llm_baseline --limit 10

# Full run on official test split (360 rows)
uv run python -m ml.llm_baseline --run-name llama3_full

# Resume interrupted run
uv run python -m ml.llm_baseline --run-name llama3_full --resume
```

Outputs per run: `reports/llm/<run_name>/llm_eval.json`, `llm_predictions.csv`, `llm_raw_responses.jsonl`  
Summary: `reports/llm/llm_runs_summary.csv`

## Artifact layout

### Official (do not modify)

```
data/
  raw/kubernetes_issues.jsonl          official raw dataset
  processed/                           OFFICIAL classifier splits (train/val/test) — LOCKED

reports/
  kubernetes_label_eda.json            official EDA
  kubernetes_*.csv                     official EDA CSVs
  split_report.json                    official split metadata
  text_quality_report.json             text quality audit
  classical/                           OFFICIAL classical baseline (LogisticRegression 0.694)
  transformer/                         transformer run reports (per-run subdirs + runs_summary.csv)
  llm/                                 LLM baseline reports (per-run subdirs + runs_summary.csv)
  official/figures/                    presentation figures 01-14 (read-only snapshot)
  artifact_manifest.json               full path manifest

artifacts/
  classical/                           best_model.joblib + metadata
  transformer/<run_name>/              model/ + model_card.json per encoder run

docs/
  CLASSIFIER_TRACK_REPORT.md          living classifier track report
```

### Failed experiments (archived — do not use as training inputs)

| Experiment | test_macro_f1 | Data | Reports |
|---|---|---|---|
| Support-only augmentation | 0.681 | `data/experiments/failed/support_augmented/` | `reports/experiments/failed/support_augmented/` |
| Cleaned splits | 0.694 (no gain) | `data/experiments/failed/cleaned_splits/` | `reports/experiments/failed/cleaned_splits/` |
| Strict text preprocessing | 0.638 | `data/experiments/failed/strict_text/` | `reports/experiments/failed/strict_text/` |

Source scripts (`ml/create_strict_text_splits.py`, `ml/clean_processed_splits.py`) remain in `ml/` as documentation.

### Archive

```
reports/archive/           legacy single-run reports (superseded)
reports/archive_numpy/     numpy project archived reports
data/archive_numpy/        numpy project archived data
```

**Rules:**
- Never delete — move to `experiments/failed/` or `archive/` instead.
- `data/processed/` is LOCKED. Do not replace it with any experiment output.
- Transformer and LLM baselines must use `data/processed/` only.
- `reports/figures/` is the live output folder; `reports/official/figures/` is a read-only snapshot.

## Tools API

Two NLP tool endpoints exposed at `/api/v1/tools/`. Both are designed to be called by the chatbot over HTTP as tool calls.

### POST /api/v1/tools/entities — NER (LIVE)

Deterministic rule-based extractor. No model inference. No GPU. No Ollama.

```bash
curl -s -X POST http://localhost:8000/api/v1/tools/entities \
  -H "Content-Type: application/json" \
  -d '{"text": "kubectl get pods fails with ImagePullBackOff on v1.29.0"}' \
  | python -m json.tool
```

Expected response shape:
```json
{
  "entities_by_type": {
    "versions": ["v1.29.0"],
    "commands": ["kubectl get pods"],
    "components": [],
    "errors": ["ImagePullBackOff"],
    "resources": [],
    "paths": [],
    "images": [],
    "urls": []
  },
  "total_count": 3
}
```

### POST /api/v1/tools/summarize — Summarization (LIVE — requires Ollama)

Structured four-part summary: **Problem / Expected / Evidence / Component**.  
Requires Ollama running locally with `llama3:latest`. Returns 503 if Ollama is unreachable.

```bash
# Start Ollama in a separate terminal first
ollama serve
ollama pull llama3:latest   # one-time

curl -s -X POST http://localhost:8000/api/v1/tools/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Pod crashlooping due to OOM on node after v1.29.0 upgrade. kubectl describe pod shows OOMKilled. Expected: pod restarts gracefully. Memory limit is 512Mi.",
    "max_chars": 400
  }' \
  | python -m json.tool
```

Expected response shape:
```json
{
  "summary": "1. Problem — ...\n2. Expected — ...\n3. Evidence — ...\n4. Component — ...",
  "model": "llama3:latest",
  "latency_seconds": 4.2
}
```

### Manual smoke check (no docker required)

```bash
# Verify app imports and start uvicorn
uv run python -c "from app.main import app; print(app.title)"
uv run uvicorn app.main:app --port 8000

# In a second terminal — NER (no Ollama needed)
curl -s -X POST http://localhost:8000/api/v1/tools/entities \
  -H "Content-Type: application/json" \
  -d '{"text": "kubectl get pods fails with ImagePullBackOff on v1.29.0"}' \
  | python -m json.tool

# Summarize (requires: ollama serve + ollama pull llama3:latest in a separate terminal)
curl -s -X POST http://localhost:8000/api/v1/tools/summarize \
  -H "Content-Type: application/json" \
  -d '{"text": "Pod crashlooping due to OOM on node after v1.29.0 upgrade. kubectl describe pod shows OOMKilled. Expected: pod restarts gracefully. Memory limit is 512Mi.", "max_chars": 400}' \
  | python -m json.tool
```

Both endpoints verified 2026-05-20: entities returns `entities_by_type + total_count`; summarize returns `summary + model=llama3:latest + latency_seconds≈18`.

### Architecture

```
schemas/tools.py          API contracts (Pydantic)
routes/tools.py           HTTP-only — no business logic, no SQLAlchemy
services/tools/__init__.py service layer — calls entity_extractor or OllamaClient
infra/ollama_client.py    async httpx client — OllamaUnavailableError on failure
domain/errors.py          ToolInputError, OllamaUnavailableError
```

Config values (base URL, timeout, model) are module-level constants in `app/infra/ollama_client.py`.

## Chatbot / Memory / Widget phase

CHAT-0 is tracking-only. CHAT-1 added the database schema foundation.

Planning docs:
- `docs/CHATBOT_TRACK_REPORT.md`
- `docs/CHATBOT_CODE_REVIEW_NOTES.md`
- `docs/MEMORY_TRACK_REPORT.md`
- `docs/WIDGET_TRACK_REPORT.md`

### CHAT-1 — Schema checks (no DB needed)

```powershell
# Verify ORM models, domain models, repositories, and migration all import cleanly
.\.venv\Scripts\python.exe -m pytest tests/unit/test_chat1_schema.py -q

# Lint
.\.venv\Scripts\python.exe -m ruff check app ml pipelines tests

# Full suite
.\.venv\Scripts\python.exe -m pytest -q
```

### CHAT-1 — Apply migration (Docker DB required)

```bash
# Run CHAT-1 schema migration against local DB
docker compose run --rm migrate
# or directly:
DATABASE_URL=postgresql+asyncpg://handyman:password@localhost:5432/handyman \
  uv run alembic upgrade head
```

Next implementation tasks:
- MEMORY-1: Implement short-term memory service with Redis TTL
- WIDGET-1: Widget config API + /widget.js loader plan

### CHAT-2 — Tool-calling chatbot API (LIVE)

Requires Groq API key in Vault at `secret/llm / groq_api_key`.

```powershell
# Lint
.\.venv\Scripts\python.exe -m ruff check app ml pipelines tests

# Unit tests (no network)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_chat_tools.py -q

# Integration tests (mocked Groq)
.\.venv\Scripts\python.exe -m pytest tests/integration/test_chat_api.py -q

# Full suite (176 tests)
.\.venv\Scripts\python.exe -m pytest -q
```

### MODEL-SERVER-1 — LogisticRegression classify route (LIVE)

`POST /classify` runs the operational fallback classifier from `artifacts/classical/best_model.joblib`.
It requires no Torch and returns 503 if the artifact is missing. `/healthz` remains available either way.

```powershell
# Lint
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests

# Full suite
.\.venv\Scripts\python.exe -m pytest -q
```

Store Groq API key in Vault:

```powershell
# 1. Capture key in shell variable
$env:GROQ_KEY = Read-Host "Paste Groq API key"

# 2. Write into Vault (secret/llm path)
docker compose exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=dev-root-token vault `
  vault kv put secret/llm groq_api_key="$env:GROQ_KEY"

# 3. Clear variable
Remove-Item Env:\GROQ_KEY
```

Smoke-test the endpoint (requires Vault with groq_api_key + API running):

```bash
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What causes CrashLoopBackOff in Kubernetes?"}' \
  | python -m json.tool
```

Architecture:

```
prompts/chat_system.md              system prompt (loaded + cached at first request)
app/infra/groq_client.py            async httpx adapter — GroqUnavailableError on failure
app/services/chat/prompts.py        system prompt loader
app/services/chat/tool_registry.py  tool definitions (OpenAI format) + dispatch()
app/services/chat/orchestrator.py   tool-calling loop — up to MAX_TOOL_ROUNDS=2
app/api/routes/chat.py              HTTP only — maps GroqUnavailableError → 503
app/api/schemas/chat.py             ChatRequest / ChatResponse / ToolCallRecord
app/domain/errors.py                GroqUnavailableError
```

## AUTH-1: JWT register/login/me (LIVE)

JWT signing key must be in Vault at `secret/handyman / jwt_signing_key`.

```powershell
# Unit + integration tests (no network required)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_auth_service.py tests/integration/test_auth_api.py -v

# Lint
.\.venv\Scripts\python.exe -m ruff check app ml pipelines tests

# Full suite
.\.venv\Scripts\python.exe -m pytest -q
```

Endpoints:

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/auth/register` | POST | none | Create new user (role=user always) |
| `/api/v1/auth/login` | POST | none | Returns JWT + user object |
| `/api/v1/auth/me` | GET | Bearer JWT | Returns current user |

Request examples (with API running):

```bash
# Register
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "strongpassword"}' \
  | python -m json.tool

# Login
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "strongpassword"}' \
  | python -m json.tool

# Me (replace TOKEN with access_token from login)
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer TOKEN" \
  | python -m json.tool
```

Architecture:

```
app/infra/security.py         PBKDF2-SHA256 password hashing; HS256 JWT (stdlib only, no PyJWT)
app/services/auth.py          register_user / login_user / get_current_user_by_id / require_role
app/api/routes/auth.py        HTTP boundary; require_authenticated_user dependency (importable)
app/api/schemas/auth.py       RegisterRequest / LoginRequest / UserPublic / LoginResponse
app/domain/auth.py            ROLE_USER/ROLE_ADMIN constants; auth error classes
```

## MEMORY-1: Redis short-term memory (LIVE)

Short-term memory stores redacted conversation context in Redis, keyed by `conversation_id`, TTL=24h.

```powershell
# Unit tests (no real Redis required)
.\.venv\Scripts\python.exe -m pytest tests/unit/test_short_term_memory.py -v

# Full suite
.\.venv\Scripts\python.exe -m pytest -q
```

Key: `memory:short_term:{conversation_id}` (Redis List)
TTL: 86400 seconds (24h), reset on every write
Max items: 50 (enforced via LTRIM)
Redaction: applied before every RPUSH

The `write_memory` chatbot tool now stores to Redis. If Redis is unreachable, the tool returns `{"status": "memory_unavailable"}` — the chat request does not fail.

```bash
# Smoke-test write_memory via chat (requires Redis + Groq key + API running)
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Remember that we prefer RBAC for access control in this cluster", "conversation_id": "demo-1"}' \
  | python -m json.tool
```

Architecture:

```
app/infra/redis_client.py             async Redis adapter; raises RedisUnavailableError
app/services/memory/config.py         MEMORY_TTL_SECONDS=86400, MEMORY_MAX_ITEMS=50, MEMORY_KEY_PREFIX
app/services/memory/short_term.py     store_memory() / read_memory() — redact before write
app/domain/memory.py                  RedisUnavailableError; role constants
app/services/chat/tool_registry.py    write_memory → store_memory(get_redis_client(), conv_id, content)
```

## RAG pipeline

All RAG pipeline modules support `--help` and exit without running the pipeline.

```powershell
# RAG-1a: Build held-out issue candidates and leakage guard
# Reads: data/raw/kubernetes_issues.jsonl, data/processed/*.csv, evals/golden/classification_golden.jsonl
# Writes: data/rag/processed/heldout_issue_candidates.jsonl, data/rag/corpus_manifest.json, reports/rag/leakage_report.json
.\.venv\Scripts\python.exe -m pipelines.rag.build_corpus

# RAG-1b/1c: Collect corpus sources (issue comments + bounded curated docs from 2 repos)
# Requires: Vault running with secret/github token, internet access
# Reads: data/rag/processed/heldout_issue_candidates.jsonl, data/processed/*.csv
# Writes: data/rag/processed/issues_with_comments.jsonl, data/rag/raw_docs/doc_sources.jsonl
#         reports/rag/corpus_collection_report.json, data/rag/corpus_manifest.json (updated)
# Results: 50 issues, 383 comments, 9 docs (kubernetes/kubernetes + kubernetes/website)
.\.venv\Scripts\python.exe -m pipelines.rag.collect_sources --max-issues 50 --max-comments-per-issue 20 --max-docs 12

# RAG-2/2b: Chunking experiments + quality filter
# Reads: data/rag/raw_docs/doc_sources.jsonl, data/rag/processed/issues_with_comments.jsonl
# Writes: data/rag/chunks/chunks_baseline_fixed.jsonl (2596 after filter)
#         data/rag/chunks/chunks_section_aware.jsonl  (2189 after filter)
#         reports/rag/chunking_report.json
#         reports/rag/chunking_examples.csv
# Quality filter: MIN_CHUNK_CHARS=40, high-signal token exception
# Chosen for next phase: section_aware
.\.venv\Scripts\python.exe -m pipelines.rag.chunk

# RAG-3a: Generate RAG golden set candidates
# Reads: data/rag/chunks/chunks_section_aware.jsonl
# Writes: evals/golden/rag/rag_golden_candidates.csv (43 candidates)
#         evals/golden/rag/rag_golden_candidates_summary.json
# validation_passed=true, all 43 chunk refs valid
.\.venv\Scripts\python.exe -m pipelines.rag.create_golden_candidates

# RAG-3 review prep: Generate review-friendly candidate file
# Reads: evals/golden/rag/rag_golden_candidates.csv
# Writes: evals/golden/rag/rag_golden_candidates_review.csv (adds answer_preview, suggested_keep, suggested_reason)
#         evals/golden/rag/rag_golden_review_summary.json (yes=25, maybe=11, no=7)
.\.venv\Scripts\python.exe -m pipelines.rag.prepare_review

# RAG-3b: Finalize golden set from curated review CSV
# Reads: evals/golden/rag/rag_golden_candidates_review.csv (selected_for_final=yes rows)
# Writes: evals/golden/rag/rag_golden.jsonl (25 rows, docs=5, issue=10, comment=10)
#         evals/golden/rag/rag_golden_summary.json (validation_passed=true)
# Validation gates: count=25, hand_labeled>=5, source mix, chunk ref validity, no dupes
.\.venv\Scripts\python.exe -m pipelines.rag.finalize_golden

# RAG-4: TF-IDF lexical baseline eval (use .venv)
# Writes: reports/rag/retrieval/tfidf_section_aware.json/.csv
#         reports/rag/retrieval/retrieval_runs_summary.csv
.\.venv\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever tfidf

# TF-IDF with technical_terms query expansion
.\.venv\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever tfidf --query-transform technical_terms

# RAG-4: Dense embedding eval (use .venv-gpu — downloads model first run)
# Best model: intfloat/e5-small-v2 (mrr@10=0.3307, hit@5=0.60)
# NOTE: e5 requires query:/passage: prefixes — handled automatically by eval_retrieval.py
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever dense --model intfloat/e5-small-v2
# Other candidates:
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever dense --model BAAI/bge-small-en-v1.5

# RAG-5: Hybrid alpha sweep — E5 (FINAL PIPELINE: alpha=0.7, hit@5=0.68, mrr@10=0.329)
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever hybrid --model intfloat/e5-small-v2 --alpha 0.3
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever hybrid --model intfloat/e5-small-v2 --alpha 0.5
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever hybrid --model intfloat/e5-small-v2 --alpha 0.7
# RAG-5b: Reranker eval over E5 hybrid — evaluated; NOT recommended (hurts E5: hit@5 0.68→0.56)
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever rerank --model intfloat/e5-small-v2 --alpha 0.7 --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
# Ablation: BGE-small hybrid sweep
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever hybrid --model BAAI/bge-small-en-v1.5 --alpha 0.7

# RAG-5: Metadata filter example (restrict to docs only)
.\.venv\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever tfidf --filter-source-type docs

# Generate comparison tables from retrieval_runs_summary.csv (use .venv)
# Writes: embedding_model_comparison.json/.csv, hybrid_alpha_comparison.json/.csv,
#         rerank_comparison.json/.csv, query_transform_comparison.json
.\.venv\Scripts\python.exe -m pipelines.rag.make_embedding_comparison
```

## RAG-6: Runtime retrieval endpoint

```powershell
# POST /api/v1/rag/query — with Docker stack running
curl -s -X POST http://localhost:8000/api/v1/rag/query `
  -H "Content-Type: application/json" `
  -d '{"question": "How does pod scheduling work in Kubernetes?", "top_k": 5}'

# TF-IDF only (CI-safe, no modelserver)
curl -s -X POST http://localhost:8000/api/v1/rag/query `
  -H "Content-Type: application/json" `
  -d '{"question": "What does Kubernetes say about Services?", "top_k": 3, "retriever": "tfidf", "query_transform": "technical_terms"}'

# Filter to docs only
curl -s -X POST http://localhost:8000/api/v1/rag/query `
  -H "Content-Type: application/json" `
  -d '{"question": "kubectl drain usage", "top_k": 3, "source_type": "docs"}'
```

Response shape: `question`, `retriever_used`, `query_transform_used`, `top_k`, `results[]`, `answer` (null until generation wired), `latency_seconds`

Architecture notes:
- api container: no torch/transformers; sklearn + numpy only
- modelserver container: Torch + transformers; serves /embed for E5 query embeddings
- retriever_used=hybrid: modelserver available; retriever_used=tfidf_fallback: modelserver down
- retriever=tfidf: force TF-IDF, skip modelserver entirely (CI-safe)

## RAG-7: CI eval harness

```powershell
# CI-safe TF-IDF eval (no modelserver, no torch)
.\.venv\Scripts\python.exe -m pipelines.rag.eval_api

# With technical_terms query expansion
.\.venv\Scripts\python.exe -m pipelines.rag.eval_api --query-transform technical_terms

# E5 hybrid eval (requires modelserver running)
.\.venv\Scripts\python.exe -m pipelines.rag.eval_api --alpha 0.7
```

TF-IDF CI baseline: hit@5=0.40, mrr@10=0.196 (n=25)
Production target (E5 hybrid): hit@5=0.68, mrr@10=0.329
Thresholds in `eval_thresholds.yaml`: rag.hit_at_5_min=0.25, rag.mrr_at_10_min=0.15

## Useful checks

```bash
# Confirm all containers healthy
docker compose ps

# Tail api logs
docker compose logs -f api

# Tail model_server logs
docker compose logs -f model_server
```
