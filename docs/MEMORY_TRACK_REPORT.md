# Memory Track Report

## 1. Short-term memory plan

Short-term memory will live in Redis and support active chat context only. It should be scoped by user/session and expire through an explicit TTL.

No short-term memory behavior is implemented in CHAT-0.

## 2. Redis TTL decision placeholder

Decision pending. The implementation phase must choose:
- default TTL
- refresh-on-message behavior
- maximum retained turns/tokens
- cleanup and observability metrics

## 3. Long-term memory type decision placeholder

Decision pending. Long-term memory types may include:
- user preferences
- project/repository facts
- stable workflow preferences
- explicit user-approved notes

The system must not infer and persist long-term memory automatically.

## 4. pgvector storage plan

Long-term memory will be stored in Postgres with pgvector embeddings for semantic lookup. The schema should keep raw/redacted text, metadata, embedding vector, owner/scope, timestamps, and audit linkage.

No migration is created in CHAT-0.

## 5. Explicit write_memory policy

Long-term memory writes must happen only through an explicit `write_memory` tool call. The model may propose a memory write, but application code must validate and execute it through the memory service.

No auto-writes from chat transcripts are allowed.

## 6. Audit-log policy

Every long-term memory write must create an audit log row. The audit row should record who/what requested the write, the redacted content reference, timestamp, source conversation/message, and action metadata.

## 7. Redaction-before-memory policy

Sensitive content must be redacted before any memory storage. Redaction should happen before Redis writes, Postgres writes, logs, traces, and audit text fields.

## 8. Open blockers

none

## 9. Next steps

1. MEMORY-1: Implement short-term memory service with Redis TTL.
2. Select Redis TTL defaults (session vs. user-scoped).
3. MEMORY-2: Long-term memory in Postgres with pgvector + audit log linkage.
