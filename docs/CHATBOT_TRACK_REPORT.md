# Chatbot Track Report

## 1. Executive summary

CHAT-0 is a tracking-only foundation for the chatbot, memory, and widget phase. No runtime chatbot, auth, memory, or widget behavior is implemented here.

The planned architecture is one FastAPI-backed tool-calling LLM shared by the Streamlit internal/admin app and a standalone React widget. The LLM may call project tools for classification, entity extraction, summarization, RAG answers, and explicit memory writes.

## 2. Requirements checklist

| Requirement | Status |
|---|---|
| Single tool-calling LLM, not multi-agent workflow | **DONE (CHAT-2)** |
| Tools wrap classifier, NER, summarizer, and RAG | **DONE (CHAT-2)** |
| Explicit `write_memory` tool, no auto-writes | **DONE (CHAT-2 — placeholder)** |
| Short-term memory in Redis with explicit TTL | Planned |
| Long-term memory in Postgres with pgvector | Planned |
| Audit log row for every long-term memory write | Planned |
| FastAPI backend shared by Streamlit and React widget | Planned |
| Streamlit internal/admin app | Planned |
| Standalone React widget bundle | Planned |
| Widget config from database | Planned |
| Loader script served from `/widget.js` | Planned |
| Host demo app | Planned |
| Origin allowlisting and CSP frame-ancestors | Later |
| Eval suites in CI | Later |

## 3. Single tool-calling LLM policy

The chatbot should be implemented as one LLM session that can call tools. It must not become a multi-agent workflow or a graph of independent LLM agents.

The LLM decides when to call tools. Application code validates tool inputs, executes service-layer functions, redacts sensitive data, and returns structured results.

## 4. Tool inventory

| Tool | Purpose | Planned backend boundary |
|---|---|---|
| `classify` | Predict issue label using classifier service | FastAPI route -> service -> classifier adapter |
| `entities` | Extract Kubernetes entities deterministically | Existing tools API/service |
| `summarize` | Produce structured issue summary | Existing tools API/service |
| `rag_answer` | Retrieve context and answer maintainer questions | Future RAG service/API |
| `write_memory` | Explicitly persist approved long-term memory | Memory API/service with audit log |

## 5. Backend API plan

FastAPI remains the shared backend for Streamlit and the React widget. Chat endpoints should live under `app/api`, delegate orchestration to `app/services`, and keep external adapters under `app/infra`.

Planned API surface:
- chat session create/read
- message send/stream
- tool execution through service layer
- memory read/write endpoints
- widget config read endpoint

## 6. Streamlit app plan

Streamlit is the internal/admin interface for demos, operational review, and configuration. It should use the same FastAPI backend as the widget rather than duplicating business logic.

Planned views:
- chat playground
- tool trace/audit view
- memory review/admin view
- widget config admin view

## 7. React widget plan

The React widget is a standalone embeddable bundle loaded through `/widget.js`. It should talk to the shared FastAPI backend and read widget configuration from the database.

The widget should support host-page embedding without requiring the host app to know internal API details.

## 8. Auth plan (CHAT-1 complete)

CHAT-1 implemented the database foundation for auth:

| Decision | Choice |
|---|---|
| Role model | Single `role` column (`user` / `admin`) on `users` table |
| Active flag | `is_active` bool on `users` — inactive users blocked at service layer |
| Auth errors | `UserNotFoundError`, `InvalidCredentialsError`, `UserAlreadyExistsError`, `InactiveUserError` in `app/domain/auth.py` |
| Widget identity | `public_widget_id` UUID on `widget_configs` — public tenant identifier for loader script |
| Widget access | `owner_user_id` FK — each widget owned by one user |
| Origin allowlisting | `allowed_origins` JSONB list — enforced by `WidgetOriginDeniedError` at service layer |
| Conversation scope | `user_id` nullable + `widget_id` nullable — session can belong to user, widget, or both |

Pending for later phases:
- API token / JWT issuance (CHAT-2)
- CSP `frame-ancestors` enforcement (WIDGET-1)
- Redis session TTL (MEMORY-1)

## 9. Memory plan

Short-term memory will use Redis with explicit TTL. Long-term memory will use Postgres plus pgvector. Long-term writes must happen only through an explicit `write_memory` tool call, and every write must create an audit log row.

Memory content must be redacted before storage.

## 10. Observability/redaction/error handling plan

Every chat turn should preserve request IDs and trace IDs. Tool calls should log metadata only, never secrets or raw sensitive values.

Errors should be structured and user-safe. Service exceptions should map to HTTP responses in routers, not inside service/repository layers.

## 11. CI/eval plan

Future CI should include:
- chat tool contract tests
- memory redaction tests
- widget config schema tests
- RAG and classifier eval gates
- smoke tests for Streamlit/backend/widget integration

## 12. Open blockers

none

## 9b. CHAT-2 implementation (complete)

CHAT-2 delivered the tool-calling chatbot API. Key decisions:

| Decision | Choice |
|---|---|
| Primary LLM | Groq `llama-3.3-70b-versatile` — OpenAI-compatible API via httpx |
| Fallback model constant | `openai/gpt-oss-20b` (configurable, not activated by default) |
| Tool loop | Up to `MAX_TOOL_ROUNDS=2` Groq calls per turn; tool errors return structured payloads, never crash the request |
| Groq key location | Vault `secret/llm` / `groq_api_key` — loaded at runtime via `_load_groq_api_key()` |
| Tool wiring | `rag_query` → `retrieve()`; `extract_entities` → `extract_entities_service()`; `summarize` → `summarize_service()` (graceful on OllamaUnavailableError); `classify_issue` → `ModelServerClient.classify()` (graceful on ModelServerUnavailableError); `write_memory` → placeholder |
| System prompt | `prompts/chat_system.md` — loaded and cached by `app/services/chat/prompts.py` |
| Tracing | Spans: `chat.request`, `llm.groq.chat`, `tool.{name}` — all inputs/outputs truncated + redacted |
| Architecture | `app/infra/groq_client.py` adapter → `app/services/chat/orchestrator.py` → `app/api/routes/chat.py` (HTTP only) |
| Test strategy | No real Groq calls; inject `_client` mock or patch `run_chat`; 30 new tests |

## 13. Next steps

1. MEMORY-1: Short-term Redis memory with explicit TTL.
2. WIDGET-1: Widget config API + `/widget.js` loader.
3. Generation eval (faithfulness/answer_relevancy via LLM judge).
