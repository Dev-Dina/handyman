# Project Brief — Canonical Implementation Contract

_This file is the single canonical contract for all remaining implementation work._
_Read this and `PROJECT_STATE.md` before every task._

## 1. Purpose and authority hierarchy

| Document | Role | Mutability |
|---|---|---|
| `AIE_Week7_Maintainers_Copilot_v4.pdf` | Original assignment brief — immutable | Read-only |
| `docs/PROJECT_BRIEF_CANONICAL.md` | Implementation contract — this file | Updated as decisions lock |
| `docs/PROJECT_BRIEF_VALIDATION.md` | Compliance gap audit | Updated as gaps close |
| `PROJECT_STATE.md` | Progress tracker | Updated after every task |
| `DECISIONS.md` | Locked technical decisions with numbers | Updated as decisions finalize |

**This file does not replace the brief — it translates it into actionable contracts given current state.**

---

## 2. Non-negotiable architecture rules

Every file, every commit, every task:

| Rule | Meaning |
|---|---|
| `app/api/` = HTTP only | Routers validate schemas, map domain errors to HTTP codes, call services. Nothing else. |
| `app/services/` = business logic | Orchestration, transactions, cache invalidation. No HTTP errors. No SQLAlchemy in args. |
| `app/repositories/` = SQL only | Raw ORM queries. No HTTP exceptions. No external API calls. No cache. |
| `app/domain/` = pure models/errors | Pydantic models, domain exceptions, enums. No imports from infra. |
| `app/infra/` = external adapters | Vault, Redis, MinIO, Groq, Ollama, modelserver, tracing, redaction. |
| No SQLAlchemy in routers | ORM models never cross the HTTP boundary. |
| No HTTPException in services/repositories | Map at the API boundary only. |
| Secrets from Vault only | `.env` holds only Vault address, root token, and ports. |
| Redaction before every output | Logs, traces, memory writes, audit text — all go through `app/infra/redaction.py`. |
| No Torch in main API / Docker | `api` container = sklearn + numpy only. Torch lives behind `model_server` boundary. |
| Torch/transformers = model_server only | `model_server/` is the inference boundary for all neural models. |

---

## 3. Locked decisions

These are decided, numbered, and not revisitable without explicit rationale.

| Decision | Value | Evidence |
|---|---|---|
| Dataset repo | kubernetes/kubernetes | `DECISIONS.md` |
| Label classes | bug / feature / docs / question | `DECISIONS.md` — LOCKED |
| Split strategy | Per-class chronological 70/15/15 | `DECISIONS.md` — LOCKED |
| Classifier primary | microsoft/codebert-base | test_macro_f1=0.7061, `artifacts/transformer/codebert_base_e3_len384/` |
| Classifier fallback | LogisticRegression (TF-IDF) | test_macro_f1=0.6938, `artifacts/classical/best_model.joblib` |
| Chatbot LLM | Groq llama-3.3-70b-versatile | `DECISIONS.md`, `app/infra/groq_client.py` |
| Groq key location | Vault `secret/llm / groq_api_key` | `app/services/chat/orchestrator.py` |
| Tool loop max rounds | MAX_TOOL_ROUNDS = 2 | `app/services/chat/orchestrator.py` |
| RAG embedding model | intfloat/e5-small-v2 | mrr@10=0.3307, hit@5=0.60; `DECISIONS.md` |
| RAG retrieval pipeline | E5 hybrid alpha=0.7 | hit@5=0.68, mrr@10=0.329; `DECISIONS.md` |
| RAG reranker | Evaluated and rejected | hurts E5: hit@5 0.68→0.56; `DECISIONS.md` |
| RAG chunk strategy | Section-aware, max 1024 chars | 2189 chunks; `DECISIONS.md` |
| Long-term memory type | Episodic | `DECISIONS.md` |
| Short-term memory TTL | 24 hours (Redis) | `DECISIONS.md` |
| Tracing backend | **TODO — not chosen** | `DECISIONS.md` says "TODO"; NoOpTracer currently wired |
| Widget bundle target | **TODO — not chosen** | `DECISIONS.md` says "TODO" |

---

## 4. Completed work (evidence required for each)

### Classifier / DL track — COMPLETE
- Dataset: `data/raw/kubernetes_issues.jsonl` (3923), splits `data/processed/` LOCKED
- Classical baseline: LR TF-IDF macro_f1=0.6938, `artifacts/classical/best_model.joblib`
- Fine-tuned CodeBERT: macro_f1=0.7061, `artifacts/transformer/codebert_base_e3_len384/`
- LLM baseline: llama3 macro_f1=0.5554, `reports/llm/llama3_full/`
- Three-way comparison: `reports/classifier_three_way_comparison.json`
- Classification golden set: `evals/golden/classification_golden.jsonl` (25 rows, validated)
- NER endpoint: `POST /api/v1/tools/entities` — rule-based, no GPU
- Summarization endpoint: `POST /api/v1/tools/summarize` — Ollama-driven, graceful 503

### Advanced RAG — COMPLETE
- Corpus: 50 issues + 383 comments + 9 docs; leakage_passed=true
- Section-aware chunking: 2189 chunks, `data/rag/chunks/chunks_section_aware.jsonl`
- Embedding comparison: 3 models; e5-small-v2 wins mrr@10=0.3307
- Hybrid retrieval: E5 alpha=0.7; hit@5=0.68, mrr@10=0.329
- Reranker: evaluated, rejected
- Query transform: `technical_terms` +8pp TF-IDF hit@5
- Metadata filtering: source_type, maintainer_only in retrieval service
- RAG golden set: `evals/golden/rag/rag_golden.jsonl` (25 rows, 5 hand-labeled)
- RAG eval harness: `pipelines/rag/eval_api.py`; CI thresholds in `eval_thresholds.yaml`
- RAG API: `POST /api/v1/rag/query`; E5 hybrid via modelserver; TF-IDF fallback

### Chatbot foundation (CHAT-0/1/2) — COMPLETE
- ORM schema: `app/infra/models.py` (User, WidgetConfig, AuditLog, Conversation, Message)
- Domain models + errors: `app/domain/auth.py`, `app/domain/widgets.py`
- Repositories: users, widget_configs, audit_logs, conversations
- Alembic migrations: 001 (baseline), 002 (chat1 schema)
- Groq client: `app/infra/groq_client.py`
- Chat service: `app/services/chat/` (orchestrator, tool_registry, prompts)
- Chat API: `POST /api/v1/chat`; tool loop; 5 tools registered
- System prompt: `prompts/chat_system.md`

### Observability / security foundation — COMPLETE
- Redaction: `app/infra/redaction.py` — tested; 5 tests pass
- Tracing adapter: `app/infra/tracing.py` — NoOpTracer; structurally OTEL-ready
- Trace/request IDs in logs: `trace_id_var`, `request_id_var`
- Domain exceptions mapped at API boundary: pattern in tools.py + chat.py
- SECURITY.md: redaction patterns documented

---

## 5. Partial work — schema complete, runtime missing

| Area | What exists | What is missing |
|---|---|---|
| Auth | ORM schema (email/hashed_password/role), domain errors, repositories | No fastapi-users, no JWT issuance, no `/auth/register`, no `/auth/login` — zero HTTP auth routes |
| classify_issue tool | `ModelServerClient.classify()` call + graceful fallback | `model_server/main.py` has only `/healthz` — no `/classify` route; classifier never actually runs |
| write_memory tool | Tool registered, returns `{"status": "memory_not_configured_yet"}` | No Redis client, no memory service, no real write path |
| Widget config | ORM schema, domain model, `WidgetConfigRepository.get_by_public_widget_id` | No HTTP route exposes it; no origin enforcement middleware |
| Allowed origins | `allowed_origins` JSONB column; `WidgetOriginDeniedError` defined | No CORS/CSP middleware enforces it |
| Audit log | `AuditLog` ORM model, `AuditLogRepository` | No write path from any service |
| Tracing | `NoOpTracer` span structure | No real backend — traces go nowhere; Friday demo requires visible trace UI |
| Classification eval gate | `eval_thresholds.yaml` has `classification.macro_f1_min=0.65` | No eval script runs `classification_golden.jsonl` against models; `reports/classification_eval_report.json` missing |
| Generation eval | `build_extractive_answer` returns text; `answer` field in RAG response | No faithfulness/answer_relevancy score; no LLM judge; required for submission block |
| MinIO | `minio_access_key`/`minio_secret_key` in Vault; MinIO in docker-compose | No `app/infra/minio_client.py`; no uploads anywhere |

---

## 6. Required remaining work before demo (priority order)

### 1. AUTH-1 — JWT register/login/me endpoints
**Why first:** All other user-facing features (Streamlit, widget config ownership, admin roles) require an authenticated user. jwt_signing_key is already in Vault. ORM schema is done.

Deliverables:
- `POST /api/v1/auth/register` — creates User, hashes password
- `POST /api/v1/auth/login` — verifies credentials, issues JWT signed with vault jwt_signing_key
- `GET /api/v1/auth/me` — returns current user from JWT
- Role guard dependency for admin-only routes
- 8+ unit + integration tests

### 2. MODEL-SERVER-1 — `/classify` route in model_server
**Why second:** classify_issue tool exists and calls modelserver; it just hits a stub. LogisticRegression artifact requires no GPU — fastest path to a functional classifier tool in chat.

Deliverables:
- Load `artifacts/classical/best_model.joblib` at model_server startup
- `POST /classify` — accepts `{title, body}`, returns `{label, confidence}`
- Graceful startup if artifact missing (log + `/classify` returns 503)
- No Torch import in model_server for this route

### 3. MEMORY-1 — Redis short-term memory service
**Why third:** Cross-conversation recall is a required Friday demo item. No memory = no recall demo.

Deliverables:
- `app/infra/redis_client.py` — async Redis adapter (TTL=24h default)
- `app/services/memory/short_term.py` — store/retrieve conversation context by session_id
- Wire `write_memory` tool to actually store (redacted) memory
- Explicit TTL; refresh-on-message behavior
- 6+ unit tests (mocked Redis)

### 4. TRACING-1 — Real tracing backend
**Why fourth:** Brief requires "open the tracing UI and walk through a real conversation's trace tree." NoOp = demo blocked.

Deliverables:
- Add Jaeger (or Honeycomb) to docker-compose (single container, no API key needed for Jaeger)
- Wire `app/infra/tracing.py` to emit real OTEL spans
- Update `DECISIONS.md` tracing backend choice + rationale
- Confirm span attributes flow: model, latency, tool names

### 5. MEMORY-2 — Long-term pgvector memory + audit log
**Why fifth:** Required by brief; episodic memory type chosen in DECISIONS.md.

Deliverables:
- Alembic migration: `memories` table with pgvector column
- `app/services/memory/long_term.py` — store/retrieve episodic memory
- Every write creates an `AuditLog` row
- Redaction applied before storage

### 6. MINIO-1 — Blob adapter + eval/retrieval snapshot uploads
Deliverables:
- `app/infra/minio_client.py` — boto3/minio SDK adapter, credentials from Vault
- Upload `reports/rag/api_eval_report.json` after CI eval run
- Upload retrieved-chunk snapshots per conversation (last N)

### 7. WIDGET-1 — Widget config API + origin enforcement + CSP
Deliverables:
- `GET /api/v1/widgets/{public_widget_id}` — read config (no auth required, public)
- Admin-only `POST/PATCH /api/v1/widgets/` routes (requires AUTH-1 role guard)
- CORS middleware enforcing `allowed_origins` from DB
- `Content-Security-Policy: frame-ancestors` header on widget routes

### 8. STREAMLIT-1 — Authenticated internal Streamlit app
**Prerequisite:** AUTH-1 must be complete first.

Deliverables:
- Login form → calls `/api/v1/auth/login` → stores JWT in session state
- Chat view → calls `POST /api/v1/chat` with JWT header
- Memory inspector — shows current Redis short-term context
- Widget config admin page — list/create/edit widget configs

### 9. WIDGET-2 — React widget + /widget.js + host demo
Deliverables:
- Vite React app in `widget/src/` — chat panel, bubble, collapsed/expanded
- Single bundled JS output served from widget container
- `GET /widget.js` loader — reads `data-widget-id`, injects iframe
- postMessage for iframe resize
- Theme from widget config at load time
- `demo/host/index.html` — pastes `<script>` tag, Friday demo host

### 10. EVALS-1 — Classification eval harness + generation judge eval + CI gates
Deliverables:
- `pipelines/classifier/eval_golden.py` — runs `classification_golden.jsonl` against all 3 models; writes `reports/classification_eval_report.json`
- Generation eval harness — faithfulness + answer_relevancy (RAGAS or frozen judge) against RAG golden set; hand-label agreement check
- CI: add eval harness runs to `.github/workflows/ci.yml`; fail on threshold breach

### 11. FINAL-DOCS — README + submission block
Deliverables:
- README.md updated with architecture diagram link, quick-start, and filled submission block
- `DECISIONS.md` tracing backend + widget bundle target filled
- `SECURITY.md` expanded with per-pattern rationale
- `EVALS.md` updated with actual metric numbers
- git tag `v0.1.0-week7`

---

## 7. What not to build

- Do not add UI before AUTH-1 is complete (Streamlit login will immediately fail without JWT).
- Do not add Torch to `api` Docker image. Classifier inference via LR artifact only — no GPU.
- Do not add new Python dependencies without explicit approval.
- Do not mark placeholder tools as implemented until runtime path is verified.
- Do not claim NoOpTracer is a tracing backend — it emits nothing.
- Do not auto-write memory from chat transcripts — only explicit `write_memory` tool calls.
- Do not modify `data/processed/` (classifier splits LOCKED) or `evals/golden/` JSONL files.
- Do not modify `reports/llm/` or classifier training artifacts.
- Do not touch Dockerfiles or docker-compose.yml without explicit task scope.

---

## 8. Definition of done by area

### Auth (AUTH-1)
- [ ] `POST /api/v1/auth/register` — 422 on bad email; 409 on duplicate
- [ ] `POST /api/v1/auth/login` — JWT issued; signed with `jwt_signing_key` from Vault
- [ ] `GET /api/v1/auth/me` — returns user from valid JWT; 401 on invalid
- [ ] Admin role guard dependency working
- [ ] 8+ tests passing; ruff clean

### Model server classify (MODEL-SERVER-1)
- [ ] `POST /classify` accepts `{title, body}`, returns `{label, confidence}`
- [ ] LR artifact loaded at startup; `/classify` returns 503 if missing
- [ ] No Torch import in this route
- [ ] Existing `/healthz` unaffected
- [ ] `classify_issue` chatbot tool returns real prediction in a smoke test

### Redis short-term memory (MEMORY-1)
- [ ] `app/infra/redis_client.py` exists with TTL support
- [ ] `write_memory` tool stores redacted content in Redis
- [ ] TTL=24h; refreshed on write
- [ ] `app/services/memory/short_term.py` retrieve returns None on cache miss (not error)
- [ ] 6+ unit tests (mocked Redis); ruff clean

### Long-term memory (MEMORY-2)
- [ ] Alembic migration adds `memories` table with vector column
- [ ] `app/services/memory/long_term.py` store/retrieve episodic memory
- [ ] Every write creates `AuditLog` row with actor/action/target/timestamp
- [ ] Redaction applied before any content stored
- [ ] 4+ unit tests; ruff clean

### MinIO blob (MINIO-1)
- [ ] `app/infra/minio_client.py` exists; credentials from Vault
- [ ] eval_report.json upload after CI eval run
- [ ] Retrieved-chunk snapshot upload per conversation

### Widget config API (WIDGET-1)
- [ ] `GET /api/v1/widgets/{public_widget_id}` returns theme/greeting/enabled_tools
- [ ] Admin create/edit routes with role guard
- [ ] CORS enforces `allowed_origins` from DB
- [ ] CSP `frame-ancestors` on widget routes

### Streamlit app (STREAMLIT-1)
- [ ] Login form works against real `/auth/login` endpoint
- [ ] Chat view works against real `/api/v1/chat` endpoint
- [ ] Memory inspector shows Redis context
- [ ] Widget config admin page (list/create/edit)

### React widget (WIDGET-2)
- [ ] Vite build produces single bundled JS
- [ ] Chat panel + bubble + expand/collapse works
- [ ] `/widget.js` loader injects iframe with `data-widget-id`
- [ ] postMessage iframe resize implemented
- [ ] Theme from widget config at load time
- [ ] `demo/host/index.html` embeds widget; Friday demo runs from this host

### Tracing (TRACING-1)
- [ ] Real backend (Jaeger recommended) in docker-compose
- [ ] `app/infra/tracing.py` emits real OTEL spans
- [ ] Span attributes: model, latency, tool name — all redacted
- [ ] `DECISIONS.md` tracing choice filled in with rationale
- [ ] Friday demo: trace tree visible in UI for a real conversation

### Evals / CI (EVALS-1)
- [ ] `pipelines/classifier/eval_golden.py` runs all 3 models; writes `reports/classification_eval_report.json`
- [ ] Generation eval: faithfulness + answer_relevancy on RAG golden set
- [ ] Hand-label agreement report (5 hand-labeled examples vs judge)
- [ ] CI runs both eval harnesses; fails if below thresholds

### Final submission (FINAL-DOCS)
- [ ] README.md filled: architecture, quickstart, submission block
- [ ] `DECISIONS.md` tracing + widget bundle target filled
- [ ] `EVALS.md` updated with actual metric numbers
- [ ] `SECURITY.md` expanded with per-pattern rationale
- [ ] git tag `v0.1.0-week7` on clean main

---

## 9. Agent instructions

Every future task must:

1. **Read first:** `PROJECT_STATE.md` + `docs/PROJECT_BRIEF_CANONICAL.md`
2. **Implement to the contract above** — not to the brief PDF directly
3. **Update `PROJECT_STATE.md`** before final response
4. **Update `docs/PROJECT_BRIEF_VALIDATION.md`** if a gap closes
5. **Never mark a phase complete** without: (a) evidence path, (b) tests passing
6. **Never close a placeholder as implemented** — placeholder ≠ runtime path
7. **Run ruff + pytest** before reporting done; quote the pass count

Stale assumptions to reject:
- "Next RAG task: wire RAG into chatbot" — DONE in CHAT-2
- "155 tests" — now 172 tests
- "answer=None for now" — now `build_extractive_answer` wired
- "thin-chunk filter reorders" — now excludes when substantive exist
