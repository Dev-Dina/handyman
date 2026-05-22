# Security

## Secrets

Secrets must resolve from Vault at startup:
- JWT signing key (`secret/handyman/jwt_signing_key`)
- DB password (`secret/handyman/database_password`)
- MinIO credentials (`secret/handyman/minio_access_key`, `minio_secret_key`)
- Tracing backend key (`secret/handyman/tracing_api_key`) — placeholder OK (Jaeger needs no key)
- Groq API key (`secret/llm/groq_api_key`) — read by chat orchestrator at call time
- GitHub token (`secret/github/token`) — read by corpus fetch pipelines

`.env` may contain only:
- Vault address (`VAULT_ADDR`)
- Vault token for local dev (`VAULT_DEV_ROOT_TOKEN`)
- Ports and non-secret local flags
- `ENVIRONMENT` mode flag

## Local dev vs production Vault

| | Local dev | Production |
|---|---|---|
| Vault mode | `server -dev` (in-memory, no TLS) | HA cluster (file/raft backend, TLS) |
| Token | `dev-root-token` (auto-seeded by vault-init.sh) | AppRole or short-lived token from CI |
| Secret provisioning | `docker/vault-init.sh` seeds placeholders at startup | Secrets provisioned before deploy; vault-init.sh NOT used |
| `ENVIRONMENT` value | `local` | `production` or `staging` |

## Placeholder refusal policy

When `ENVIRONMENT=production` or `ENVIRONMENT=staging`, the app refuses to start if:

| Condition | Error |
|---|---|
| `VAULT_DEV_ROOT_TOKEN=dev-root-token` | Startup error — real Vault token required |
| `jwt_signing_key` contains `local-dev` or `change-in-prod` | Startup error — real signing key required |

Implementation: `app/core/config.py` `Settings._assert_production_secrets()` runs after Vault secrets load.
Error messages name the secret key only, never its value.

`llm_api_key` at `secret/handyman` is a reference placeholder — the live Groq key for chat is
at `secret/llm/groq_api_key` (a separate path). A placeholder `llm_api_key` does NOT block production startup;
chat will fail at call time with `GroqUnavailableError` if the real key is missing.

## Redaction

Redaction must run before:
- logs
- traces
- memory writes
- audit details
- retrieved chunk snapshots

Implementation: `app/infra/redaction.py`

## Redaction patterns (rationale)

| Pattern | Rationale |
|---|---|
| API keys (`sk-`, `gsk_`, `Bearer `) | Groq and OpenAI-format keys appear in Authorization headers and inline references; leak enables billing fraud |
| GitHub tokens (`ghp_`, `github_pat_`) | PAT grants repo access; leak enables unauthorized fetch or write |
| JWTs (3-part base64 dot-separated) | A leaked JWT allows impersonation of any registered user until expiry |
| Authorization headers | The entire header value is a credential — not just the token part |
| Passwords | Plain-text password in log/trace would give account access on any system reusing the password |
| Private keys (PEM blocks) | Private key leak is permanent credential compromise — cannot be rotated without key replacement |
| Emails | PII; also used as login credential |
| URLs with tokens | OAuth and pre-signed URLs embed credentials as query parameters |

## Verified test

A fake secret in a user message must not appear unredacted in:
- logs
- traces
- memory rows

See `tests/unit/test_redaction.py` — 5 redaction tests pass.

## Do not use dev-root-token in production

`dev-root-token` is a well-known default hardcoded in every Vault dev-mode startup.
Using it in production exposes full Vault access to anyone who knows this default.
The production hardening check in `app/core/config.py` explicitly refuses it.
