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

## Testing

```powershell
# Full suite (61 tests — safe: no Docker, no Ollama, no network)
.\.venv\Scripts\python.exe -m pytest -q

# Dry run (collect only)
.\.venv\Scripts\python.exe -m pytest --collect-only

# By category
.\.venv\Scripts\python.exe -m pytest tests/unit        # 35 pure-function tests
.\.venv\Scripts\python.exe -m pytest tests/smoke       # 8 import/route sanity checks
.\.venv\Scripts\python.exe -m pytest tests/integration # 10 FastAPI endpoint tests (Ollama mocked)
.\.venv\Scripts\python.exe -m pytest tests/eval        # 8 golden CSV schema/quality gates
.\.venv\Scripts\python.exe -m pytest tests/build       # 9 compose/config structural checks

# By marker
.\.venv\Scripts\python.exe -m pytest -m unit
.\.venv\Scripts\python.exe -m pytest -m "not build"
```

See `tests/README.md` for category definitions and rules.

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

CHAT-0 is tracking-only. No chatbot, auth, memory, Streamlit, widget, loader, or host demo commands exist yet.

Planning docs:
- `docs/CHATBOT_TRACK_REPORT.md`
- `docs/CHATBOT_CODE_REVIEW_NOTES.md`
- `docs/MEMORY_TRACK_REPORT.md`
- `docs/WIDGET_TRACK_REPORT.md`

Next implementation tasks:
- Design auth + widget config database schema
- Wire classifier/RAG tools behind API endpoints
- Implement short-term memory service with Redis TTL

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
