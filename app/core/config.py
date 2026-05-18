from functools import lru_cache

from pydantic import PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.errors import VaultUnavailableError  # noqa: F401 — re-raised at boot

_REQUIRED_KEYS = (
    "jwt_signing_key",
    "database_password",
    "minio_access_key",
    "minio_secret_key",
    "llm_api_key",
    "tracing_api_key",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vault_addr: str = "http://localhost:8200"
    vault_dev_root_token: str

    _secrets: dict[str, str] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _load_from_vault(self) -> "Settings":
        from app.infra.vault_client import VaultClient

        client = VaultClient(addr=self.vault_addr, token=self.vault_dev_root_token)
        for key in _REQUIRED_KEYS:
            self._secrets[key] = client.get_secret(key)
        return self

    def secret(self, key: str) -> str:
        """Return a Vault-loaded secret by name. Never logs the value."""
        return self._secrets[key]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
