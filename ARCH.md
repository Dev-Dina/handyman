# Architecture

## Required services
- api: FastAPI app for auth, chat, memory, RAG orchestration, widget config
- model_server: FastAPI inference server for classifier, NER, summarizer
- chatbot: Streamlit app for authenticated users/admins
- widget: React/Vite embeddable widget bundle
- host: demo host app
- migrate: Alembic migration container
- db: Postgres 16 + pgvector
- redis: short-term memory/cache
- minio: blob storage
- vault: secrets

## Python backend layers

### app/api
HTTP only:
- routers
- request/response schemas
- dependency injection
- exception mapping

Cannot import:
- SQLAlchemy models directly
- Redis clients directly
- Vault clients directly
- MinIO clients directly
- LLM provider clients directly

### app/services
Business logic:
- chat orchestration
- auth use cases
- memory operations
- widget config operations
- RAG orchestration
- classifier tool orchestration

### app/repositories
SQL only:
- users
- conversations
- memories
- widgets
- audit logs
- documents/chunks

No HTTP exceptions.
No cache invalidation.
No external APIs.

### app/domain
Pure models/errors:
- domain exceptions
- Pydantic domain models
- enums

### app/infra
External adapters:
- Vault client
- Redis client
- MinIO client
- tracing
- redaction
- LLM client
- model server HTTP client
- embedding client

## Request flow
```
HTTP request -> api route -> service -> repository/infra -> service -> api response
```
