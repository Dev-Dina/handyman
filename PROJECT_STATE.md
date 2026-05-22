# Project State

## Project
Week 7 Maintainer's Copilot

## Deadline
Thursday night working demo, Friday 10-minute presentation.

## Current phase
Phase 1 - DL/NLP track — **COMPLETE (closed 2026-05-21)**

## Chosen repo
kubernetes/kubernetes

---

## Current official classifier status

| Track | Model | test_macro_f1 | test_accuracy | Status |
|---|---|---|---|---|
| Classical baseline | LogisticRegression (TF-IDF) | 0.6938 | 0.7139 | LOCKED — fallback |
| Best transformer | microsoft/codebert-base | 0.7061 | 0.7500 | LOCKED — PRIMARY |
| LLM baseline | llama3:latest (Ollama) | 0.5554 | 0.5850 | LOCKED |

**Final deployment decision: CodeBERT primary, LogisticRegression operational fallback.**

Official data: `data/processed/` — LOCKED (1680 train / 360 val / 360 test, 420/90/90 per class)

Failed experiments archived: `data/experiments/failed/` + `reports/experiments/failed/`

---

## Where to find things

| What | Path |
|---|---|
| Official figures (presentation) | `reports/official/figures/` (01-18) |
| EDA + classical reports | `reports/classical/`, `reports/kubernetes_*.json/csv` |
| Transformer run reports | `reports/transformer/` (per-run subdirs) |
| Transformer runs summary | `reports/transformer/transformer_runs_summary.csv` |
| LLM baseline reports | `reports/llm/` (per-run subdirs) |
| LLM runs summary | `reports/llm/llm_runs_summary.csv` |
| Failed experiment reports | `reports/experiments/failed/` |
| Raw dataset | `data/raw/kubernetes_issues.jsonl` |
| Official splits | `data/processed/train.csv`, `val.csv`, `test.csv` |
| Classical model artifact | `artifacts/classical/best_model.joblib` |
| Transformer model artifacts | `artifacts/transformer/<run_name>/` |
| Living classifier report | `docs/CLASSIFIER_TRACK_REPORT.md` |
| Reports README | `reports/README.md` |
| Reports inventory | `reports/report_inventory.csv`, `reports/report_inventory.json` |
| Reports map notebook | `notebooks/00_reports_map.py` |
| Classifier experiments review notebook | `notebooks/01_classifier_experiments_review.py` |
| RAG retrieval review notebook | `notebooks/02_rag_retrieval_review.py` |
| Full path manifest | `reports/artifact_manifest.json` |
| Canonical implementation brief | `docs/PROJECT_BRIEF_CANONICAL.md` |
| Brief compliance validation | `docs/PROJECT_BRIEF_VALIDATION.md` |

---

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
- [x] reports/text_quality_report.json
- [x] ml/make_eda_figures.py (6 PNG figures in reports/figures/)
- [x] Classical ML baseline (TF-IDF + LogisticRegression, accuracy 0.713889, macro_f1 0.693839)
- [x] Classical model comparison (6 models, best=LogisticRegression, val_macro_f1 0.701875, test_macro_f1 0.693839)
- [x] Support-only augmentation experiment (ABLATION — not adopted; test_macro_f1 0.680766 < baseline 0.693839, question F1 0.272727; archived to data/experiments/failed/)
- [x] Cleaned splits experiment (ABLATION — no gain, 0.693839 = baseline; archived to data/experiments/failed/)
- [x] Strict text preprocessing experiment (ABLATION — worst, 0.637926; archived to data/experiments/failed/)
- [x] ml/finetune.py - manual PyTorch loop (AdamW + DataLoader); no Trainer/TrainingArguments/datasets/pandas/numpy; saves best by val macro-F1; --run-name/--reports-dir per-run isolation; writes reports/transformer/<run_name>/transformer_{eval,training_history}.json + artifacts/transformer/<run_name>/; appends reports/transformer/transformer_runs_summary.csv
- [x] Create .venv-gpu (CUDA, local), torch.cuda.is_available()=True, CUDA GPU verified
- [x] Transformer encoder comparison: bert-tiny/electra-small/codebert-base/minilm-l12 — COMPLETE; best=microsoft/codebert-base test_macro_f1=0.7061
- [x] docs/CLASSIFIER_TRACK_REPORT.md — living classifier report created
- [x] ml/make_classifier_figures.py — 5 classifier figures (10-14) in reports/official/figures/
- [x] ml/classifier_config.py — centralized constants (LABELS, paths, known metrics, Ollama defaults); used by finetune.py, llm_baseline.py, make_classifier_figures.py, compare_classical.py
- [x] LLM baseline run — llama3_full COMPLETE; macro_f1=0.5554, accuracy=0.5850; reports/llm/llama3_full/
- [x] Three-way comparison — reports/classifier_three_way_comparison.json/csv + figures 15-18
- [x] Final deployment decision — CodeBERT primary, LogisticRegression fallback
- [x] Classification golden set candidates — evals/golden/classification_golden_candidates.csv (48 rows, 12/class)
- [x] Classification golden set curated — evals/golden/classification_golden_curated.csv (25 rows, gold_label + curator_notes filled)
- [x] Classification golden set FINAL — evals/golden/classification_golden.jsonl (25 rows, validated; bug=7, feature=6, docs=6, question=6)
- [x] Tools API architecture — schemas, routes, infra scaffold (app/api/schemas/, app/api/routes/, app/infra/ollama_client.py)
- [x] NER endpoint — POST /api/v1/tools/entities LIVE; calls extract_entities_service
- [x] Summarization endpoint — POST /api/v1/tools/summarize LIVE; Problem/Expected/Evidence/Component prompt via OllamaClient; 503 on unavailable
- [x] Tools API smoke check — POST /entities verified (entities_by_type + total_count); POST /summarize verified (summary + model=llama3:latest + latency_seconds=18.39)
- [x] Path hygiene cleanup — app/core/paths.py canonical roots; classifier/RAG configs derive from canonical paths; scripts run as modules without project-root sys.path hacks

### Official classifier dataset

```
data/processed/train.csv — 1680 rows, 420/class  (LOCKED)
data/processed/val.csv   — 360 rows, 90/class    (LOCKED)
data/processed/test.csv  — 360 rows, 90/class    (LOCKED)
```

Failed experiment data (archived — do not use as training inputs):

```
data/experiments/failed/support_augmented/   augmentation — rejected, F1 0.681
data/experiments/failed/cleaned_splits/      cleaned splits — no gain, F1 0.694
data/experiments/failed/strict_text/         strict preprocessing — rejected, F1 0.638
```

### Env separation
- Main env (.venv via uv): no Torch, no accelerate. Runs app, tests, classical ML.
- GPU env (.venv-gpu, local only): Torch CUDA, transformers, accelerate. Runs finetune.py.
- Docker: no Torch. Never install Torch in Dockerfiles.

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

## Test organization

| Category | Path | Count | Status |
|---|---|---|---|
| unit | tests/unit/ | 201 | 201/201 PASS |
| smoke | tests/smoke/ | 20 | 20/20 PASS |
| integration | tests/integration/ | 77 | 77/77 PASS |
| eval | tests/eval/ | 24 | 24/24 PASS |
| build | tests/build/ | 2 | 2/2 PASS |
| **Total** | | **323** | **323/323 PASS** |

Markers registered in pyproject.toml: `unit`, `smoke`, `integration`, `eval`, `build`.
See `tests/README.md` for category definitions and run commands.

> **Future implementation must follow `docs/PROJECT_BRIEF_CANONICAL.md`.**

## Current blockers
none

## Advanced RAG

| Phase | Scope | Status |
|---|---|---|
| RAG-0 | Tracking, config, folder structure | **COMPLETE (2026-05-21)** |
| RAG-1a | Corpus manifest + leakage guard | **COMPLETE (2026-05-21)** |
| RAG-1b | Source collection: docs + issue comments | **COMPLETE (2026-05-21)** |
| RAG-1c | Expanded docs: kubernetes/website curated paths | **COMPLETE (2026-05-21)** |
| RAG-2 | Chunking experiments | **COMPLETE (2026-05-21)** |
| RAG-3 | RAG golden set (25 examples) | **COMPLETE (2026-05-21)** — rag_golden.jsonl (25 rows, docs=5, issue=10, comment=10) |
| RAG-4 | Embedding model comparison | **COMPLETE (2026-05-21)** — e5-small-v2: mrr@10=0.3307, hit@5=0.60 (wins all 3 candidates) |
| RAG-5 | Retrieval experiments (hybrid, reranking, query transformation) | **COMPLETE (2026-05-21)** — E5 hybrid alpha=0.7: hit@5=0.68, mrr@10=0.329 (best overall; reranker rejected) |
| RAG-6 | Service / API integration | **COMPLETE (2026-05-21)** — POST /api/v1/rag/query live; E5 hybrid via modelserver; TF-IDF fallback |
| RAG-7 | Eval + exception/redaction hardening | **COMPLETE (2026-05-21)** — eval harness + thresholds + thin-chunk filter + extractive answer + tracing spans + schema hardening; 172/172 tests pass |

### RAG implementation status

- [x] RAG-0: app/services/rag/config.py (canonical), app/services/rag/__init__.py, docs/RAG_TRACK_REPORT.md, docs/RAG_CODE_REVIEW_NOTES.md, data/rag/ dirs, reports/rag/ dirs, evals/golden/rag/
- [x] RAG-1a: pipelines/rag/build_corpus.py — 1498 held-out candidates; leakage_passed=true; corpus_manifest.json
- [x] RAG-1b: pipelines/rag/collect_sources.py — issue comments + bounded docs; corpus_collection_report.json; manifest updated
- [x] RAG-1c: expanded DOC_SOURCES to kubernetes/website; 9 docs from 2 repos; --max-docs/--include-website-docs args; failed_doc_paths in report
- [x] RAG-2: pipelines/rag/chunk.py — baseline_fixed + section_aware chunkers; chunking_report.json + chunking_examples.csv; chosen=section_aware
- [x] RAG-2b: quality filter (MIN_CHUNK_CHARS=40, high-signal token exception); baseline 2781->2596, section_aware 2623->2189; new report fields: dropped_tiny_chunks, min_char_length_after_filter, min_chunk_chars, tiny_chunk_policy
- [x] RAG-3a: pipelines/rag/create_golden_candidates.py — 43 candidates (docs=8, issue=20, comment=15); validation_passed=true; evals/golden/rag/rag_golden_candidates.csv + summary.json
- [x] RAG-3 review prep: pipelines/rag/prepare_review.py — rag_golden_candidates_review.csv (yes=25, maybe=11, no=7); answer_preview + suggested_keep + suggested_reason added; rag_golden_review_summary.json
- [x] RAG-3b: pipelines/rag/finalize_golden.py — rag_golden.jsonl (25 rows, docs=5, issue=10, comment=10, hand_labeled=5, validation_passed=true); rag_golden_summary.json
- [x] RAG pipeline CLI/static cleanup — sys imports restored where needed; offline pipeline --help exits without running generation/fetch/chunk logic
- [x] RAG-4: pipelines/rag/eval_retrieval.py — TF-IDF + dense eval; all 3 candidates evaluated; e5-small-v2 WINS mrr@10=0.3307, hit@5=0.60; embedding_model_comparison.json
- [x] RAG-5: BGE hybrid sweep + E5 hybrid sweep (RAG-5b); E5 hybrid alpha=0.7 BEST: hit@5=0.68, mrr@10=0.329, latency=5.4s; reranker evaluated and rejected for E5 (−12pp hit@5); technical_terms +8pp TF-IDF; metadata filter scaffold
- [x] RAG-5 reports: hybrid_alpha_comparison.json, rerank_comparison.json, query_transform_comparison.json, retrieval_runs_summary.csv (14 runs)
- [x] RAG-6: POST /api/v1/rag/query — E5 hybrid alpha=0.7 via modelserver; TF-IDF fallback; metadata filters; 8 integration tests + 3 smoke tests; 73/73 pass
- [x] RAG-7: eval harness (pipelines/rag/eval_api.py; hit@5=0.40, mrr@10=0.196 TF-IDF CI baseline); eval_thresholds.yaml; canonical response schema (results, retriever_used, query_transform_used, answer); shared query_transform module; thin-chunk filter (now excludes thin chunks when substantive exist); extractive answer (build_extractive_answer, top 3 non-thin chunks, 1200 chars max, no LLM); tracing spans; generic 500 handler; 172/172 pass

### Next 3 tasks

1. EVALS-1: Generation judge eval (faithfulness/answer_relevancy on RAG golden set 5 hand-labeled rows).
2. FINAL-DOCS: README + submission block + git tag `v0.1.0-week7`.
3. SECURITY.md: fill per-pattern rationale defense (brief requires it).

## Chatbot + Memory + Widget

| Phase | Scope | Status |
|---|---|---|
| CHAT-0 | Tracking foundation | **COMPLETE (2026-05-21)** |
| CHAT-1 | Auth + widget config schema design | **COMPLETE (2026-05-21)** |
| CHAT-2 | Tool-calling chatbot API and tool wrappers | **COMPLETE (2026-05-21)** |
| MEMORY-1 | Short-term Redis memory with explicit TTL | **COMPLETE (2026-05-22)** |
| MEMORY-2 | Long-term Postgres/pgvector memory + audit log | **COMPLETE (2026-05-22)** |
| DB-PGVECTOR-1 | pgvector extension + vector(384) embedding migration + IVFFlat index | **COMPLETE (2026-05-22)** |
| MINIO-1 | MinIO blob adapter + artifact/eval/retrieval snapshot upload pipeline | **COMPLETE (2026-05-22)** |
| STREAMLIT-1 | Authenticated Streamlit chat app + memory API endpoints | **COMPLETE (2026-05-22)** |
| WIDGET-1 | Widget config API + origin/CSP enforcement | **COMPLETE (2026-05-22)** |
| WIDGET-2 | React widget bundle + host demo app | **COMPLETE (2026-05-22)** |

### Chatbot implementation status

- [x] CHAT-0: tracking docs created — `docs/CHATBOT_TRACK_REPORT.md`, `docs/CHATBOT_CODE_REVIEW_NOTES.md`, `docs/MEMORY_TRACK_REPORT.md`, `docs/WIDGET_TRACK_REPORT.md`
- [x] CHAT-1: ORM models (User+is_active, WidgetConfig structured, AuditLog renamed, Conversation+widget_id); domain models; `app/domain/auth.py`; `app/domain/widgets.py`; repositories (WidgetConfigRepository, AuditLogRepository); `alembic/versions/002_chat1_schema.py`; 17 unit tests
- [x] CHAT-2: POST /api/v1/chat — Groq llama-3.3-70b-versatile; tools: rag_query/extract_entities/summarize/classify_issue/write_memory (placeholder); `app/infra/groq_client.py`; `app/services/chat/` (orchestrator, tool_registry, prompts); `app/api/routes/chat.py`; `prompts/chat_system.md`; 33 new tests (21 unit + 12 integration); classify_issue calls live model_server `/classify`
- [x] AUTH-1: JWT register/login/me endpoints — POST /api/v1/auth/register, POST /api/v1/auth/login, GET /api/v1/auth/me; PBKDF2-SHA256 password hashing; HS256 JWT (stdlib only); `app/infra/security.py`; `app/services/auth.py`; `app/api/routes/auth.py`; `require_authenticated_user` dependency + `require_role` guard; 29 new tests (17 unit + 12 integration); 205/205 pass
- [x] MODEL-SERVER-1: `/classify` route in model_server — LogisticRegression TF-IDF fallback via `artifacts/classical/best_model.joblib`; no Torch import; 4 unit tests
- [x] MEMORY-1: Redis short-term memory service — `app/infra/redis_client.py`; `app/services/memory/short_term.py`; `store_memory`/`read_memory`; TTL=24h; redaction before RPUSH; `write_memory` tool wired (real Redis); 8 unit tests (fake client)
- [x] TRACING-1: Real Jaeger/OTEL tracing — `OtelTracerWrapper` in `app/infra/tracing.py`; `configure_tracing()` at lifespan; OTLP HTTP → Jaeger; Jaeger in docker-compose (UI :16686, OTLP :4318); `DECISIONS.md` updated; 4 new unit tests; 218/218 pass
- [x] TRACING-1b: Test noise fix — removed `ConsoleSpanExporter` fallback (was spawning `BatchSpanProcessor` background thread that flushed to closed stdout after pytest); OTLP package absent → NoOpTracer kept silently; `provider.shutdown()` added to OTEL wrapper test; 218/218 pass clean
- [x] MEMORY-2: Long-term Postgres episodic memory + audit log — `app/services/memory/long_term.py` (`store_long_term_memory`, `list_long_term_memories`, `store_long_term_memory_with_db`); `app/repositories/memories.py` + `list_by_conversation`; `alembic/versions/003_memory2_long_term.py` (user_id nullable + conversation_id + memory_type + log_metadata); `write_memory` tool routes by `scope` param; 14 new unit tests
- [x] DB-PGVECTOR-1: pgvector embedding — `alembic/versions/004_pgvector_embedding.py` (CREATE EXTENSION vector + ALTER embedding to vector(384) + IVFFlat index); `MEMORY_EMBEDDING_DIM=384` constant; `pgvector>=0.3.0` in pyproject.toml; `pgvector/pgvector:pg16` DB image (was already set); conditional ORM import (`PGVECTOR_AVAILABLE` flag); 15 new tests (14 unit + 1 build); 246/246 pass
- [x] MINIO-1: Blob storage adapter + artifact upload pipeline — `app/infra/minio_client.py` (MinioClient: ensure_bucket/upload_file/upload_json/stat_object; lazy minio import; secrets from Vault); `app/domain/blob.py` (MinioUnavailableError); `app/services/blob/config.py` (bucket/prefix/content-type constants); `app/services/blob/storage.py` (upload_json/upload_file/upload_retrieval_snapshot with redaction + tracing); `pipelines/blob/upload_artifacts.py` (CLI; skip missing; --dry-run; --include-model-artifacts; writes reports/blob/upload_summary.json); `minio>=7.2.0` in pyproject.toml; 32 new unit tests; 278/278 pass
- [x] CI-1: deterministic CI + eval gates — `.github/workflows/ci.yml` uses `uv sync --extra dev --extra ml --extra chatbot` (never `--all-extras`); asserts no Torch; runs ruff, LR classification golden eval, TF-IDF RAG eval, and pytest; `pipelines/classifier/eval_golden.py`; `reports/classification_eval_report.json` macro_f1=0.6691, accuracy=0.7200; `reports/rag/api_eval_report.json` hit@5=0.4000, mrr@10=0.1960; 284/284 pass
- [x] CI-2: modular CI jobs — 11 independent jobs: ci-assets, lint, tests-unit, tests-smoke, tests-integration, tests-eval, tests-build, classifier-golden-eval (needs ci-assets), rag-golden-eval (needs ci-assets), widget-build (npm ci + npm run build), docker-compose-config; `scripts/check_ci_assets.py`; lint now covers scripts + notebooks; 323/323 pass
- [x] CI-3: eval jobs now fail explicitly (not silently skip) when assets absent — `if: always()` + explicit `needs.ci-assets.result` gate on classifier-golden-eval and rag-golden-eval; ruff + assets pass
- [x] CI-4: fix tests-build exit code 5 — root cause: `build/` in .gitignore matched `tests/build/`; added `!tests/build/` + `!tests/build/**` exceptions; changed CI command from `pytest -m build` to `pytest tests/build` (pytest default norecursedirs includes "build"); updated RUNBOOK + EVALS; 323/323 pass
- [x] WIDGET-AUDIT-1: npm audit — 2 moderate vulns (esbuild ≤ 0.24.2, vite ≤ 6.4.1, GHSA-67mh-4wv8-2f99); dev-server only, production bundle unaffected; `npm audit fix` no-ops (only `--force` fix available, breaks vite@8); deferred; DECISIONS.md bundle target filled (145,290 bytes raw / ~47.05 kB gzip); RUNBOOK.md audit warning added
- [x] REPORTS-AND-NOTEBOOKS-1: reports audit/review layer — `scripts/audit_reports.py`; `reports/README.md`; `reports/report_inventory.csv/json`; marimo notebooks `notebooks/00_reports_map.py`, `01_classifier_experiments_review.py`, `02_rag_retrieval_review.py`; documentation/indexing only, no artifacts deleted, moved, renamed, retrained, or fetched
- [x] STREAMLIT-1: Authenticated Streamlit chat app — `chatbot/main.py` (login, chat, memory inspector, widget admin placeholder); `chatbot/config.py` + `chatbot/api_client.py` (httpx sync); `app/api/routes/memory.py` (GET /short-term + /long-term, auth-gated, graceful Redis fallback); `app/api/schemas/memory.py`; 8 integration tests; 292/292 pass
- [x] WIDGET-1: Widget config API + origin enforcement + CSP; 22 new tests; 314/314 pass
- [x] WIDGET-2: React widget bundle + `/widget.js` loader + host demo app; `widget/src/` Vite+React; `app/api/routes/widget_loader.py`; `demo/host/index.html`; 9 smoke tests; 323/323 pass
- [ ] Generation eval: faithfulness/answer_relevancy via LLM judge (after CHAT functional)
- [ ] Classifier eval harness: runs classification_golden.jsonl against all 3 models

## Backlog (post-RAG, not blocking)
- POST /api/v1/tools/classify — wire CodeBERT inference endpoint via model_server
- Integrate classify/entities/summarize into chatbot as callable tool calls
- Eval test for classification_golden.jsonl JSONL schema (field presence, label validity)
- CI gates for eval tests
- model_server/container hardening

## Commands
```bash
uv run pytest
docker compose up --build

# Dataset pipeline
uv run python -m ml.fetch_dataset --repo kubernetes/kubernetes --per-class 1000
uv run python -m ml.eda_labels
uv run python -m ml.split_dataset --max-per-class 600
uv run python -m ml.text_preprocessing
uv run python -m ml.classical_baseline
uv run python -m ml.classical.compare_classical

# Path hygiene audit (2026-05-21)
git status --short
Get-Content AGENTS.md
Get-Content PROJECT_STATE.md
Get-ChildItem -Recurse -File | Select-String -Pattern 'Path\(__file__\)\.resolve\(\)\.parent\.parent','Path\(__file__\)\.resolve\(\)\.parents\[','\bROOT\s*=','\bPROJECT_ROOT\s*=','\bBASE_DIR\s*='
Get-ChildItem -Recurse -File | Select-String -Pattern 'Path\(__file__\)\.parent\.parent'
.\.venv\Scripts\python.exe -c "from app.core.paths import PROJECT_ROOT; print(PROJECT_ROOT)"
.\.venv\Scripts\python.exe -m ml.finetune --help
.\.venv\Scripts\python.exe -m ml.llm_baseline --help
.\.venv\Scripts\python.exe -m ml.classical.compare_classical --help
.\.venv\Scripts\python.exe -m pipelines.rag.chunk --help
.\.venv\Scripts\python.exe -m pytest tests/unit tests/smoke tests/eval -q
.\.venv\Scripts\python.exe -m pytest -q

# RAG pipeline CLI/static cleanup (2026-05-21)
.\.venv\Scripts\python.exe -m ruff check pipelines/rag app ml tests
.\.venv\Scripts\python.exe -m pipelines.rag.build_corpus --help
.\.venv\Scripts\python.exe -m pipelines.rag.collect_sources --help
.\.venv\Scripts\python.exe -m pipelines.rag.chunk --help
.\.venv\Scripts\python.exe -m pipelines.rag.create_golden_candidates --help
.\.venv\Scripts\python.exe -m pipelines.rag.prepare_review --help
.\.venv\Scripts\python.exe -m pipelines.rag.finalize_golden --help

# CHAT-0 tracking foundation (2026-05-21)
.\.venv\Scripts\python.exe -m ruff check docs app ml pipelines tests
.\.venv\Scripts\python.exe -m pytest tests/unit tests/smoke tests/eval -q

# MODEL-SERVER-1 classify fallback (2026-05-21)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q

# MEMORY-1 Redis short-term memory (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q

# TRACING-1 Jaeger/OTEL tracing (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q
docker compose config

# MEMORY-2 long-term Postgres memory + audit log (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q

# DB-PGVECTOR-1 pgvector embedding schema (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q
docker compose config

# MINIO-1 blob adapter + artifact upload pipeline (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests
.\.venv\Scripts\python.exe -m pytest -q
docker compose config

# STREAMLIT-1 authenticated Streamlit app + memory API (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests chatbot chatbot_streamlit
.\.venv\Scripts\python.exe -m pytest -q
# start app: .\.venv\Scripts\python.exe -m streamlit run chatbot/main.py

# WIDGET-2 React widget bundle + /widget.js loader + host demo (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests chatbot
.\.venv\Scripts\python.exe -m pytest -q
# build widget: cd widget && npm install && npm run build && cd ..
# open demo: start demo\host\index.html

# CI-1 deterministic CI + eval gates (2026-05-22)
.\.venv\Scripts\python.exe -m ruff check app model_server ml pipelines tests chatbot
.\.venv\Scripts\python.exe -m pipelines.classifier.eval_golden
.\.venv\Scripts\python.exe -m pipelines.rag.eval_api
.\.venv\Scripts\python.exe -m pytest -q

# REPORTS-AND-NOTEBOOKS-1 audit/review layer (2026-05-22)
.\.venv\Scripts\python.exe scripts/audit_reports.py
.\.venv\Scripts\python.exe -m ruff check scripts notebooks
.\.venv\Scripts\python.exe -m pytest -q
```

```powershell
# Transformer fine-tuning (GPU env — not uv)
.\.venv-gpu\Scripts\python.exe -m ml.finetune --smoke
.\.venv-gpu\Scripts\python.exe -m ml.finetune --model microsoft/codebert-base --run-name codebert_base_e3_len384 --epochs 3 --batch-size 4 --max-len 384

# RAG-4/5 retrieval evals (GPU env for dense, cpu env for tfidf)
.\.venv\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever tfidf
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever dense --model BAAI/bge-small-en-v1.5
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever hybrid --model BAAI/bge-small-en-v1.5 --alpha 0.7
.\.venv-gpu\Scripts\python.exe -m pipelines.rag.eval_retrieval --retriever rerank --model BAAI/bge-small-en-v1.5 --alpha 0.7 --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
.\.venv\Scripts\python.exe -m pipelines.rag.make_embedding_comparison
```
