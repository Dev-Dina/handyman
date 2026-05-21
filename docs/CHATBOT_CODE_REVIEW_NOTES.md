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

## Intentionally not implemented yet

Not included in CHAT-0:
- chatbot endpoint
- tool-calling prompt/runtime
- auth
- database schema or migrations
- Redis memory service
- pgvector memory storage
- Streamlit app
- React widget bundle
- `/widget.js`
- host demo app
- origin allowlisting or CSP
- CI eval suites

## Code review talking points

1. CHAT-0 prevents the chatbot, memory, and widget work from becoming tangled.
2. The architecture keeps one LLM and explicit tools, avoiding multi-agent complexity.
3. Memory writes are planned as explicit `write_memory` tool calls only.
4. The same FastAPI backend will serve Streamlit and the React widget.
5. Security and observability are planned before implementation: redaction, audit logs, origin controls, and eval gates.
