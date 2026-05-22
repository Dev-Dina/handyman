from functools import lru_cache

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.errors import VaultUnavailableError  # noqa: F401 — re-raised at boot

_REQUIRED_KEYS = (
    "jwt_signing_key",
    "database_password",
    "minio_access_key",
    "minio_secret_key",
    # llm_api_key at secret/handyman is a reference placeholder; the active Groq key
    # used by the chat orchestrator lives at secret/llm/groq_api_key (separate path).
    "llm_api_key",
    "tracing_api_key",
)

# Patterns that identify local-dev placeholder values.
_PLACEHOLDER_PATTERNS: tuple[str, ...] = ("placeholder", "local-dev", "change-in-prod")

# Environment values that trigger production hardening checks.
_PROD_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod", "staging"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vault_addr: str = "http://localhost:8200"
    vault_dev_root_token: str
    environment: str = "local"

    _secrets: dict[str, str] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _load_from_vault(self) -> "Settings":
        from app.infra.vault_client import VaultClient

        client = VaultClient(addr=self.vault_addr, token=self.vault_dev_root_token)
        for key in _REQUIRED_KEYS:
            self._secrets[key] = client.get_secret(key)
        self._assert_production_secrets()
        return self

    def _assert_production_secrets(self) -> None:
        """Raise ValueError if placeholder/dev secrets are present in a non-local env.

        Error messages are safe: they name the secret key, not its value.
        """
        if self.environment.lower() not in _PROD_ENVIRONMENTS:
            return

        if self.vault_dev_root_token == "dev-root-token":
            raise ValueError(
                f"ENVIRONMENT={self.environment} refuses VAULT_DEV_ROOT_TOKEN='dev-root-token'. "
                "Set a real Vault token or configure AppRole auth before deploying."
            )

        jwt_key = self._secrets.get("jwt_signing_key", "")
        if any(p in jwt_key for p in _PLACEHOLDER_PATTERNS):
            raise ValueError(
                f"ENVIRONMENT={self.environment} refuses a placeholder jwt_signing_key. "
                "Provision a real signing key in Vault at secret/handyman before deploying."
            )

    def secret(self, key: str) -> str:
        """Return a Vault-loaded secret by name. Never logs the value."""
        return self._secrets[key]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
