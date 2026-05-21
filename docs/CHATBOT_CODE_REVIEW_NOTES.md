# Chatbot Code Review Notes

## Scope

CHAT-0 creates planning and tracking documents only. It does not implement chatbot runtime behavior, auth, memory persistence, Streamlit, or the React widget.

## Why one tool-calling LLM

The chatbot should be one LLM with a clear tool inventory, not a multi-agent application. This keeps behavior auditable, easier to test, and aligned with the project requirement for a single tool-calling LLM.

Application code should not simulate agents or create hidden model-to-model workflows. It should expose validated tools, execute them through service boundaries, and return structured outputs to the LLM.

## Tool and service boundaries

Tools should call FastAPI/service-layer boundaries:
- API routes validate HTTP contracts and map domain errors to HTTP responses.
- Services contain business logic and tool orchestration.
- Repositories contain SQL only.
- Infra adapters wrap external systems such as Ollama, Redis, Postgres/vector search, or model servers.

The Streamlit admin app and React widget should both use the FastAPI backend. They should not duplicate classifier, RAG, memory, or summarization logic.

## Connection to existing work

Existing foundations:
- Classifier constants and scripts are centralized under `ml/classifier_config.py`.
- NER and summarization already exist under the tools API.
- RAG config and offline pipelines exist under `app/services/rag/config.py` and `pipelines/rag/`.
- Canonical paths now come from `app/core/paths.py`.

The future chatbot tools should wrap these capabilities rather than reimplement them.

## CHAT-1 schema decisions

CHAT-1 added the database foundation without any HTTP endpoints or business logic.

Key design decisions:
- `role` column (string) on `users` instead of a separate `roles` table — appropriate for two roles (user/admin); extend later if needed
- `is_active` on `users` — deactivate accounts without deleting; service layer enforces
- `public_widget_id` (UUID) on `widget_configs` — separate from internal `id` so external callers never see internal PKs
- `allowed_origins` as JSONB list — flexible for multi-origin tenants; enforcement is service-layer not DB constraint
- `actor_user_id` (nullable) on `audit_logs` — supports system-initiated audit entries with no user
- `log_metadata` Python attribute maps to `metadata` DB column — avoids shadowing `DeclarativeBase.metadata`
- `user_id` nullable + `widget_id` nullable on `conversations` — widget sessions don't require authenticated users

## CHAT-2 implementation decisions

CHAT-2 added the POST /api/v1/chat tool-calling endpoint.

Key decisions:
- **GroqClient** — httpx-based adapter; `PRIMARY_MODEL = "llama-3.3-70b-versatile"`; raises `GroqUnavailableError` on connection/timeout/HTTP errors; never logs the api_key
- **`_load_groq_api_key()`** — independent vault call to `secret/llm / groq_api_key`; separate from main `get_settings()` flow to avoid mixing paths
- **`run_chat()` injectable client** — `_client: GroqClient | None = None` parameter enables test injection without vault; production builds the client from vault
- **Tool loop max 2 rounds** — `MAX_TOOL_ROUNDS=2` constant; after 2 rounds, uses whatever answer the model has; prevents infinite tool-call loops
- **Tool errors as structured payloads** — every tool catch returns JSON to the LLM (e.g. `{"error": "summarize_unavailable"}`); the request does not fail with 500
- **`write_memory` placeholder** — returns `{"status": "memory_not_configured_yet"}`; no DB write; MEMORY-1 will implement the real service
- **`classify_issue` graceful fallback** — catches `ModelServerUnavailableError` and returns `{"status": "tool_unavailable", ...}` so the LLM is informed without crashing
- **`add classify` to ModelServerClient** — added `POST /classify` method alongside existing `embed`; same error handling pattern
- **Trace spans** — `chat.request` wraps the turn; `llm.groq.chat` wraps each LLM call (with round number); `tool.{name}` per tool; all attribute values truncated+redacted before setting

## Intentionally not implemented yet

Not included in CHAT-0, CHAT-1, or CHAT-2:
- JWT/token issuance
- Redis memory service (MEMORY-1)
- pgvector memory storage (MEMORY-2)
- Streamlit app
- React widget bundle
- `/widget.js`
- host demo app
- origin allowlisting middleware or CSP
- CI eval suites
- full conversation persistence to DB (conversations stored in CHAT-1 schema but not wired in CHAT-2)

## Code review talking points

1. CHAT-0 prevents the chatbot, memory, and widget work from becoming tangled.
2. The architecture keeps one LLM and explicit tools, avoiding multi-agent complexity.
3. Memory writes are planned as explicit `write_memory` tool calls only.
4. The same FastAPI backend will serve Streamlit and the React widget.
5. Security and observability are planned before implementation: redaction, audit logs, origin controls, and eval gates.
