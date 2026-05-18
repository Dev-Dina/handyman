#!/bin/sh
# Seeds all required secrets into Vault at secret/handyman (KV v2).
# Runs once at startup; VAULT_ADDR and VAULT_TOKEN are injected by docker-compose.
set -e

vault kv put secret/handyman \
  database_password="${DB_PASSWORD}" \
  jwt_signing_key="local-dev-jwt-signing-key-change-in-prod" \
  llm_api_key="${LLM_API_KEY:-placeholder-set-real-key-in-vault}" \
  minio_access_key="${MINIO_ROOT_USER}" \
  minio_secret_key="${MINIO_ROOT_PASSWORD}" \
  tracing_api_key="${TRACING_API_KEY:-placeholder-set-real-key-in-vault}"

echo "vault-init: secrets written to secret/handyman"
