# Project Brief Validation Audit

_Generated 2026-05-21. Compare PROJECT_STATE.md against Week 7 Maintainer's Copilot brief._

Status key: **COMPLETE** | **PARTIAL** | **TODO** | **BLOCKED** | **NOT_REQUIRED_FOR_DEMO**

---

## 1. Classifier / DL Track

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Closed issue dataset | Closed issues from one repo | `data/raw/kubernetes_issues.jsonl` (3923 issues) | **COMPLETE** | none | — |
| Label mapping (bug/feature/docs/question) | 4-class mapping in DECISIONS.md | `DECISIONS.md` label table, locked | **COMPLETE** | none | — |
| Stratified chronological splits | Test newer than train per class | `data/processed/` 1680/360/360, per-class chronological | **COMPLETE** | none | — |
| Classical ML baseline | Classical model on same splits | LR TF-IDF macro_f1=0.6938, `artifacts/classical/best_model.joblib` | **COMPLETE** | none | — |
| Fine-tuned transformer | Small encoder fine-tuned, model card | CodeBERT macro_f1=0.7061, `artifacts/transformer/codebert_base_e3_len384/` | **COMPLETE** | none | — |
| LLM baseline | Same test split, three-way comparison | llama3 macro_f1=0.5554, `reports/llm/llama3_full/` | **COMPLETE** | none | — |
| Three-way comparison | accuracy, macro-F1, per-class F1, latency, cost | `reports/classifier_three_way_comparison.json/csv`, figures 15-18 | **COMPLETE** | none | — |
| Deployment decision | Defended in DECISIONS.md | CodeBERT primary, LR fallback, documented | **COMPLETE** | none | — |
| Classification golden set (25 examples) | Hand-curated, separate from test split | `evals/golden/classification_golden.jsonl` (25 rows, validated) | **COMPLETE** | none | — |
| Classification eval pipeline | Macro-F1, per-class F1, confusion matrix — all 3 models | No eval script runs golden.jsonl against all 3 models; `reports/classification_eval_report.json` missing | **PARTIAL** | No `pipelines/classifier/eval_golden.py` script; threshold in `eval_thresholds.yaml` exists but no CI test exercises it against model predictions | Write classifier eval harness; output `reports/classification_eval_report.json` |
| NER endpoint | FastAPI, chatbot calls over HTTP | `POST /api/v1/tools/entities` live, calls `extract_entities_service` | **COMPLETE** | none | — |
| Summarization endpoint | FastAPI, pre-trained or LLM-driven | `POST /api/v1/tools/summarize` live, Ollama-driven, graceful 503 | **COMPLETE** | none | — |
| Freeze policy documented | Document and defend freeze policy | `DECISIONS.md` — full fine-tune, no freezing, rationale given | **COMPLETE** | none | — |

---

## 2. Advanced RAG

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Corpus: docs + held-out issues/comments | Project docs + resolved issues with maintainer answers | 50 issues + 383 comments + 9 docs; `data/rag/` | **COMPLETE** | none | — |
| No leakage from classifier splits | Held-out issues ≠ classifier data | `reports/rag/leakage_report.json` — leakage_passed=true, all overlaps=0 | **COMPLETE** | none | — |
| Non-naive chunking strategy | Not fixed-size only | Section-aware 2189 chunks vs fixed-size 2596; `data/rag/chunks/` | **COMPLETE** | none | — |
| Embedding model comparison with numbers | Hit@5 or MRR@10 vs ≥1 alternative | 3 models compared on 25 golden examples; e5-small-v2 wins mrr@10=0.3307 | **COMPLETE** | none | — |
| Hybrid retrieval with tuned weighting | Sparse + dense, tuned alpha | E5 hybrid alpha=0.7 hit@5=0.68, mrr@10=0.329 | **COMPLETE** | none | — |
| Cross-encoder reranking | Over top-k from hybrid | Evaluated (BGE+E5); rejected for final pipeline — documented | **COMPLETE** | none | — |
| Query transformation | HyDE or equivalent | `technical_terms` deterministic expansion +8pp TF-IDF hit@5 | **COMPLETE** | none | — |
| Metadata filtering | Over corpus | `source_type`, `maintainer_only` filters in retrieval service | **COMPLETE** | none | — |
| RAG golden set (25 examples) | question/ideal-answer/ground-truth-chunks triples | `evals/golden/rag/rag_golden.jsonl` (25 rows, 5 hand-labeled) | **COMPLETE** | none | — |
| Retrieval eval with thresholds | Retrieval metrics; CI gate | `pipelines/rag/eval_api.py`; `eval_thresholds.yaml`; `reports/rag/api_eval_report.json` | **COMPLETE** | none | — |
| Generation eval (faithfulness/answer_relevancy) | RAGAS or frozen judge; report agreement with hand labels | `DEFERRED` — noted in RAG_TRACK_REPORT; `build_extractive_answer` gives extractive text but no LLM judge wired | **PARTIAL** | No faithfulness/answer_relevancy score; no judge agreement report; required for submission block | Write generation eval harness after CHAT is functional |
| RAG API endpoint | Runtime retrieval service | `POST /api/v1/rag/query` live; TF-IDF fallback; tracing spans | **COMPLETE** | none | — |

---

## 3. Chatbot

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Single tool-calling LLM | One LLM, not multi-agent | Groq llama-3.3-70b-versatile with tool loop MAX_TOOL_ROUNDS=2 | **COMPLETE** | none | — |
| LLM provider decision documented | Defended in DECISIONS.md | DECISIONS.md has Groq choice with rationale | **COMPLETE** | none | — |
| Prompts version-controlled | `prompts/` directory | `prompts/chat_system.md` checked in | **COMPLETE** | none | — |
| Tools wrap classifier | classify_issue tool | `classify_issue` → `ModelServerClient.classify()`; `model_server/main.py` exposes `POST /classify` backed by `artifacts/classical/best_model.joblib` LogisticRegression TF-IDF fallback; no Torch import required | **COMPLETE** | none | — |
| Tools wrap NER | extract_entities tool | `extract_entities` → `extract_entities_service()` directly | **COMPLETE** | none | — |
| Tools wrap summarizer | summarize tool | `summarize` → `summarize_service()` with OllamaUnavailableError graceful | **COMPLETE** | none | — |
| Tools wrap RAG pipeline | rag_query tool | `rag_query` → `retrieve()` directly | **COMPLETE** | none | — |
| Explicit write_memory tool | No auto-writes | `write_memory` placeholder registered; returns `memory_not_configured_yet` | **PARTIAL** | placeholder only — no real write path | MEMORY-1 |
| No multi-agent workflow | One LLM, explicit tools | Tool loop is single LLM; no agent-to-agent calls | **COMPLETE** | none | — |

---

## 4. Authentication

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| fastapi-users with JWT | Email/password registration; JWT auth | ORM schema only (`users` table with `email`, `hashed_password`, `role`) — no fastapi-users integration, no JWT router, no `/auth/register`, no `/auth/login` | **TODO** | No auth endpoints exist at all | Implement auth routes (register/login/me) with JWT issuance |
| JWT signing key from Vault | Resolved at startup | `jwt_signing_key` loaded in `config.py` `_REQUIRED_KEYS` — key IS in Vault; no endpoint uses it yet | **PARTIAL** | Key in Vault; no issuance path wired | Wire JWT issuance to auth endpoint |
| Registration/login endpoints | Email + password | No HTTP auth routes exist | **TODO** | — | AUTH-1 |
| user/admin roles | Two roles; admin configures widgets | `role` column in `users` ORM model; role-checking logic not implemented | **PARTIAL** | schema complete; no enforcement in any endpoint | Role guard on admin routes |
| Admin invite/configure widgets | Admin-only widget config page | No admin endpoints; `WidgetConfigRepository` exists but no HTTP route | **TODO** | — | AUTH-1 + WIDGET-1 |

---

## 5. Memory

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Redis short-term memory with explicit TTL | Active chat context; TTL justified | No Redis infra adapter exists (`app/infra/redis_client.py` missing); no memory service | **TODO** | TTL=24h chosen in DECISIONS.md but not implemented | MEMORY-1 |
| Long-term memory in Postgres + pgvector | At least one of episodic/semantic/procedural | `app/repositories/memories.py` exists (schema) but no vector column migration, no memory service | **TODO** | No pgvector migration; no memory service | MEMORY-2 |
| Memory type chosen and defended | Defend in DECISIONS.md | `DECISIONS.md` — episodic, TTL=24h, rationale given | **COMPLETE** | none | — |
| Explicit write_memory only | No auto-writes | Tool registered as placeholder | **PARTIAL** | placeholder only | MEMORY-1 |
| Audit log for long-term writes | Actor/action/target/timestamp row | `AuditLog` ORM model exists (`app/infra/models.py`), `AuditLogRepository` exists — no write path from memory service | **PARTIAL** | schema complete; no write path | wire in MEMORY-2 |
| Redaction before memory writes | Redact before Redis/Postgres/audit | `app/infra/redaction.py` live; memory writes don't exist yet | **PARTIAL** | pattern established; no storage to redact yet | apply when MEMORY-1/2 implemented |
| Cross-conversation recall demo readiness | Demo on Friday | No Redis store, no memory service, no recall path | **TODO** | — | MEMORY-1 first |

---

## 6. Widget / UI

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Streamlit auth'd internal app | Login, full chat, memory inspector, widget config | `chatbot/main.py` is 4-line placeholder: `st.title` + `st.write` | **TODO** | entirely absent | WIDGET-1 (auth first) |
| Memory inspector | Streamlit view of memory state | Not implemented | **TODO** | — | after MEMORY-1 |
| Widget config admin page | Admin creates/edits widgets, sees embed snippet | Not implemented | **TODO** | — | WIDGET-1 |
| React standalone widget | Vite bundle, chat panel, bubble | `widget/index.html` is 5-line HTML placeholder; no React/Vite project | **TODO** | — | WIDGET-2 |
| `/widget.js` loader script | Host pastes `<script>` tag | Not implemented | **TODO** | — | WIDGET-2 |
| Host demo app | `demo/host/` static server container | `demo/host/.gitkeep` only | **TODO** | — | WIDGET-2 |
| Widget config from DB at runtime | Widget reads config from API | `WidgetConfigRepository.get_by_public_widget_id` exists — no HTTP route exposes it | **PARTIAL** | schema + repo complete; no HTTP route | WIDGET-1 |
| postMessage resize channel | At minimum iframe resize | Not implemented | **TODO** | — | WIDGET-2 |
| Allowed origins CORS enforcement | From DB, not hardcoded env | `allowed_origins` JSONB column in schema; `WidgetOriginDeniedError` defined — no middleware enforces it | **PARTIAL** | schema complete; no enforcement | WIDGET-1 |
| CSP frame-ancestors header | Per-widget allowed origins | Not implemented | **TODO** | — | WIDGET-1 |

---

## 7. Observability / Security

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| Tracing spans for LLM/tool/RAG | Every call is a span | `NoOpTracer` with spans: `chat.request`, `llm.groq.chat`, `tool.{name}`, `rag.retrieve`, etc. | **PARTIAL** | NoOpTracer emits no real traces — DECISIONS.md says "Tracing backend: TODO"; Friday demo requires opening a real trace UI | Choose + wire real tracing backend |
| Trace IDs in logs | Logs joinable with traces | `trace_id_var` used in structlog | **COMPLETE** | none | — |
| Redaction before logs/traces/memory | Tested explicitly | `app/infra/redaction.py`; 5 redaction tests pass | **COMPLETE** | none | — |
| Domain exceptions at API boundary | Structured error with code+request_id | Pattern established in tools.py, chat.py routes | **COMPLETE** | none | — |
| No stack traces in API responses | User-safe errors | Generic `except Exception → 500` with `detail` only | **COMPLETE** | none | — |
| SECURITY.md | Defend redaction patterns | `SECURITY.md` exists — patterns listed; brief says "defend the list" more thoroughly | **PARTIAL** | Existing content is a plan, not a defense | Expand with per-pattern rationale |
| grep for `sk-` / `password` in app/ | Zero matches outside Vault code | Not verified in this audit | **PARTIAL** | Should be clean given redaction tests | Run grep as part of CI |
| Real tracing backend + Friday demo | Walk trace tree in UI | Not wired — NoOp only | **TODO** | DECISIONS.md: "Tracing backend: TODO" | Choose backend (Jaeger/Honeycomb); add to docker-compose |

---

## 8. MinIO / Blob

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| MinIO adapter | `app/infra/minio_client.py` | Does not exist; `minio_access_key`/`minio_secret_key` loaded from Vault in config but no client | **TODO** | MinIO service defined in docker-compose; no Python adapter | Write MinIO infra adapter |
| Model artifacts/manifests in MinIO | Stored at build/CI time | Artifacts exist locally; not uploaded to MinIO | **TODO** | — | after MinIO adapter |
| eval_report.json stored in MinIO after CI run | Written every run, stored in blob | CI only writes to filesystem; no upload step | **TODO** | — | after MinIO adapter |
| Training plots in MinIO | Stored at training time | Local only | **TODO** | — | after MinIO adapter |
| Retrieved chunks snapshots | Per-conversation last-N snapshots | Not implemented | **TODO** | — | after MEMORY-1 |

---

## 9. CI / Submission Readiness

| Requirement | Brief expectation | Evidence / path | Status | Gap | Next action |
|---|---|---|---|---|---|
| `eval_thresholds.yaml` | Committed; thresholds non-zero | `eval_thresholds.yaml` committed; classification.macro_f1_min=0.65, rag.hit_at_5_min=0.25 | **COMPLETE** | none | — |
| Classification eval CI gate | CI runs eval and fails if below threshold | RAG eval gate exists in `tests/eval/`; **no classification eval harness** — threshold in yaml but never checked against real predictions | **TODO** | threshold committed but nothing computes it | Write classifier eval harness |
| RAG eval CI gate | CI runs RAG eval and fails if below threshold | `tests/eval/test_rag_eval_schema.py` checks `api_eval_report.json` if present; `pipelines/rag/eval_api.py` produces it | **COMPLETE** | none | — |
| Redaction test | Test proves secret never logs unredacted | 5 redaction tests pass | **COMPLETE** | none | — |
| CI on every push | lint, type-check, build images, eval suites, redaction, smoke | `.github/workflows/ci.yml` runs lint + tests; no docker build step; no image build CI; no MinIO/Vault in CI | **PARTIAL** | no docker image build or stack smoke in CI | add docker build and stack smoke |
| Fresh clone path | `docker compose up` after `cp .env.example .env` | `docker-compose.yml` exists; `.env.example` present | **COMPLETE** | none | — |
| README contains ARCH/DECISIONS/RUNBOOK/EVALS/SECURITY | All docs present | `ARCH.md`, `DECISIONS.md`, `RUNBOOK.md`, `EVALS.md`, `SECURITY.md` all exist | **COMPLETE** | none | — |
| Tag `v0.1.0-week7` | Public repo, tagged | Not yet created | **TODO** | — | tag at submission |
| DECISIONS.md — tracing backend | "Pick a tracing backend and defend the choice" | `DECISIONS.md` says "Tracing backend: TODO" | **TODO** | Not chosen or defended | Choose + document Jaeger or Honeycomb |
| DECISIONS.md — widget bundle target | Bundle size target | `DECISIONS.md` says "Widget bundle target: TODO" | **TODO** | — | set target after React build |
| Submission block filled in | Name/repo/tag/dataset/F1/RAG/mem-type/tracing/bundle-size | All fields present | **PARTIAL** | tracing + widget bundle + faithfulness score missing | fill after implementation |

---

## Summary

| Category | COMPLETE | PARTIAL | TODO | BLOCKED |
|---|---|---|---|---|
| Classifier/DL | 11 | 1 | 0 | 0 |
| Advanced RAG | 10 | 1 | 0 | 0 |
| Chatbot | 7 | 1 | 0 | 0 |
| Auth | 0 | 2 | 3 | 0 |
| Memory | 1 | 3 | 3 | 0 |
| Widget/UI | 0 | 3 | 8 | 0 |
| Observability | 4 | 3 | 1 | 0 |
| MinIO/Blob | 0 | 0 | 5 | 0 |
| CI/Submission | 5 | 2 | 4 | 0 |

---

## Recommended next 5 tasks (priority order)

### 1. AUTH-1 — JWT auth endpoints (highest brief priority)
Register/login/me with JWT issuance. `jwt_signing_key` is already in Vault. Schema is done (CHAT-1). No library additions needed if using python-jose (already a common dep) or authlib. This unblocks Streamlit login, admin roles, and widget config ownership.

### 2. MEMORY-1 — Redis short-term memory service
Write `app/infra/redis_client.py` + `app/services/memory/short_term.py`. Wire `write_memory` tool to store conversation context with TTL=24h. Unblocks cross-conversation recall demo on Friday.

### 3. TRACING-1 — Real tracing backend
Choose Jaeger (easiest: one docker-compose service, no API key) or Honeycomb. Wire `app/infra/tracing.py` to emit real OTEL spans. Required for Friday demo walk-through of trace tree.

### 4. STREAMLIT-1 — Authenticated Streamlit app (minimum viable)
Chat view + login form calling JWT auth endpoints. No memory inspector or widget admin needed for the initial pass. This is the demo surface; needs AUTH-1 first.

### 5. WIDGET-1 — Widget config API + origin enforcement
Expose widget config from the database and enforce allowed origins before building the React widget.

---

## Stale items found in PROJECT_STATE.md

| Location | Stale content | Correction |
|---|---|---|
| `### Next RAG tasks` | "Wire RAG retrieval into chatbot as callable tool (CHAT-2)" | DONE in CHAT-2 — `rag_query` already calls `retrieve()`. Remove this item. |
| `## Test organization` | Test counts were 155 before RAG fix; now 172 | Updated to 172 in this audit session |
| `RUNBOOK.md` | "Full suite (155 tests)" in test commands | Stale — now 172 tests |
| `RUNBOOK.md: CHAT-2 section` | "Full suite (155 tests)" | Stale — now 172 tests |
| `CHAT-2 chatbot implementation status` | "30 new tests (21 unit + 12 integration)" | Actually 33 new tests (21+12=33) |
| `RAG-7 status line` | "96/96 tests pass" | Stale — total is 172/172 after RAG fix |
