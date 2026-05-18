# Security

## Secrets
Secrets must resolve from Vault at startup:
- JWT signing key
- LLM API keys
- DB password
- MinIO credentials
- tracing backend keys

.env may contain:
- Vault address
- Vault root token for local dev
- ports
- non-secret local flags

## Redaction
Redaction must run before:
- logs
- traces
- memory writes
- audit details
- retrieved chunk snapshots

## Redaction patterns
- API keys
- GitHub tokens
- JWTs
- Authorization headers
- passwords
- private keys
- emails
- URLs with tokens

## Required test
A fake secret in a user message must not appear unredacted in:
- logs
- traces
- memory rows
