"""
Seed Vault with placeholder secrets for local dev.
Run once after `docker compose up`:
    uv run python scripts/bootstrap_vault.py
"""

import os
import sys

import hvac

VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://localhost:8200")
VAULT_TOKEN = os.environ.get("VAULT_DEV_ROOT_TOKEN", "dev-root-token")
MOUNT = "secret"
PATH = "handyman"

PLACEHOLDER_SECRETS = {
    "jwt_signing_key": "REPLACE_ME_jwt_signing_key",
    "database_password": "REPLACE_ME_db_password",
    "minio_access_key": "REPLACE_ME_minio_access",
    "minio_secret_key": "REPLACE_ME_minio_secret",
    "llm_api_key": "REPLACE_ME_llm_api_key",
    "tracing_api_key": "REPLACE_ME_tracing_api_key",
}


def main() -> None:
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)

    if not client.is_authenticated():
        print(f"ERROR: Cannot authenticate to Vault at {VAULT_ADDR}", file=sys.stderr)
        sys.exit(1)

    # Enable KV v2 if not already mounted
    mounts = client.sys.list_mounted_secrets_engines()
    if f"{MOUNT}/" not in mounts:
        client.sys.enable_secrets_engine(
            backend_type="kv", path=MOUNT, options={"version": "2"}
        )
        print(f"Enabled KV v2 at '{MOUNT}/'")
    else:
        print(f"KV mount '{MOUNT}/' already exists — skipping enable")

    client.secrets.kv.v2.create_or_update_secret(
        mount_point=MOUNT,
        path=PATH,
        secret=PLACEHOLDER_SECRETS,
    )
    print(f"Wrote placeholder secrets to {MOUNT}/{PATH}")
    print("Replace REPLACE_ME_* values with real secrets before non-dev use.")


if __name__ == "__main__":
    main()
