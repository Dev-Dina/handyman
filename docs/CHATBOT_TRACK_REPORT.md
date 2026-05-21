# Chatbot Track Report

## 1. Executive summary

CHAT-0 is a tracking-only foundation for the chatbot, memory, and widget phase. No runtime chatbot, auth, memory, or widget behavior is implemented here.

The planned architecture is one FastAPI-backed tool-calling LLM shared by the Streamlit internal/admin app and a standalone React widget. The LLM may call project tools for classification, entity extraction, summarization, RAG answers, and explicit memory writes.

## 2. Requirements checklist

| Requirement | Status |
|---|---|
| Single tool-calling LLM, not multi-agent workflow | Planned |
| Tools wrap classifier, NER, summarizer, and RAG | Planned |
| Explicit `write_memory` tool, no auto-writes | Planned |
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

## 8. Auth plan

Auth is not implemented in CHAT-0. The next design task should decide:
- admin/internal auth model
- widget tenant/site identity
- API token/session handling
- widget config access rules
- later origin allowlisting and CSP frame-ancestors policy

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

## 13. Next steps

1. Design auth + widget config database schema.
2. Wire classifier/RAG tools behind API endpoints.
3. Implement short-term memory service with Redis TTL.
