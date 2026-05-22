#!/bin/sh
# =============================================================================
# LOCAL DEV BOOTSTRAP ONLY — not for production Vault provisioning.
#
# This script seeds placeholder and dev-only secrets into a Vault dev-mode
# server started by docker-compose. It is intentionally simple and uses
# hardcoded placeholder values that are safe for local Docker demo only.
#
# Production deployment expects secrets already provisioned in a real Vault
# instance (HA mode, not dev mode). Do NOT use this script or the dev-root-token
# for production. See RUNBOOK.md "Production deployment" section.
#
# Secrets seeded here:
#   secret/handyman:
#     database_password     — from DB_PASSWORD env (compose default: localdev)
#     jwt_signing_key       — PLACEHOLDER — must be replaced before prod deploy
#     llm_api_key           — reference placeholder; real Groq key at secret/llm
#     minio_access_key      — from MINIO_ROOT_USER env
#     minio_secret_key      — from MINIO_ROOT_PASSWORD env
#     tracing_api_key       — placeholder (Jaeger needs no API key)
#
# Secrets NOT seeded here (must be provisioned manually):
#   secret/llm/groq_api_key     — real Groq API key for chat
#   secret/github/token         — GitHub token for corpus fetch
# =============================================================================
set -e

vault kv put secret/handyman \
  database_password="${DB_PASSWORD}" \
  jwt_signing_key="local-dev-jwt-signing-key-change-in-prod" \
  llm_api_key="${LLM_API_KEY:-placeholder-set-real-key-in-vault}" \
  minio_access_key="${MINIO_ROOT_USER}" \
  minio_secret_key="${MINIO_ROOT_PASSWORD}" \
  tracing_api_key="${TRACING_API_KEY:-placeholder-set-real-key-in-vault}"

echo "vault-init: local-dev secrets written to secret/handyman (NOT for production)"
