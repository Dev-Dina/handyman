"""Unit tests: production-mode Settings validation refuses placeholder secrets.

Tests Settings() directly (not get_settings()) to avoid lru_cache side effects.
VaultClient is patched at the hvac.Client level so no real Vault is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

_PLACEHOLDER_JWT = "local-dev-jwt-signing-key-change-in-prod"
_REAL_JWT = "a-real-jwt-signing-key-that-is-long-enough"
_PLACEHOLDER_LLM = "placeholder-set-real-key-in-vault"
_REAL_LLM = "gsk_real_groq_key_abc123"
_DEV_TOKEN = "dev-root-token"
_PROD_TOKEN = "s.production-vault-token"

_BASE_SECRETS: dict[str, str] = {
    "jwt_signing_key": _REAL_JWT,
    "database_password": "realdbpassword",
    "minio_access_key": "realaccesskey",
    "minio_secret_key": "realsecretkey",
    "llm_api_key": _REAL_LLM,
    "tracing_api_key": "realtracingkey",
}


def _make_settings(
    environment: str,
    vault_token: str,
    secrets: dict[str, str],
):
    """Instantiate Settings with a mocked Vault client."""
    from app.core.config import Settings

    with patch("app.infra.vault_client.hvac.Client") as mock_class:
        mock_hvac = MagicMock()
        mock_hvac.is_authenticated.return_value = True
        mock_hvac.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": secrets}
        }
        mock_class.return_value = mock_hvac
        return Settings(
            vault_dev_root_token=vault_token,
            environment=environment,
        )


def test_local_mode_accepts_dev_token_and_placeholder_jwt():
    settings = _make_settings(
        environment="local",
        vault_token=_DEV_TOKEN,
        secrets={**_BASE_SECRETS, "jwt_signing_key": _PLACEHOLDER_JWT},
    )
    assert settings.secret("jwt_signing_key") == _PLACEHOLDER_JWT


def test_local_mode_accepts_placeholder_llm_key():
    settings = _make_settings(
        environment="local",
        vault_token=_DEV_TOKEN,
        secrets={**_BASE_SECRETS, "llm_api_key": _PLACEHOLDER_LLM},
    )
    assert settings.secret("llm_api_key") == _PLACEHOLDER_LLM


def test_prod_mode_rejects_dev_vault_token():
    with pytest.raises(ValueError, match="dev-root-token"):
        _make_settings(
            environment="production",
            vault_token=_DEV_TOKEN,
            secrets=_BASE_SECRETS,
        )


def test_staging_mode_rejects_dev_vault_token():
    with pytest.raises(ValueError, match="dev-root-token"):
        _make_settings(
            environment="staging",
            vault_token=_DEV_TOKEN,
            secrets=_BASE_SECRETS,
        )


def test_prod_mode_rejects_local_dev_jwt():
    with pytest.raises(ValueError, match="jwt_signing_key"):
        _make_settings(
            environment="production",
            vault_token=_PROD_TOKEN,
            secrets={**_BASE_SECRETS, "jwt_signing_key": _PLACEHOLDER_JWT},
        )


def test_prod_mode_rejects_change_in_prod_jwt():
    with pytest.raises(ValueError, match="jwt_signing_key"):
        _make_settings(
            environment="prod",
            vault_token=_PROD_TOKEN,
            secrets={**_BASE_SECRETS, "jwt_signing_key": "any-change-in-prod-key"},
        )


def test_prod_mode_accepts_real_secrets():
    settings = _make_settings(
        environment="production",
        vault_token=_PROD_TOKEN,
        secrets=_BASE_SECRETS,
    )
    assert settings.secret("jwt_signing_key") == _REAL_JWT
    assert settings.environment == "production"


def test_prod_mode_accepts_placeholder_llm_key():
    """llm_api_key at secret/handyman is a reference placeholder; real Groq key
    is at secret/llm/groq_api_key. Production mode must NOT block on this."""
    settings = _make_settings(
        environment="production",
        vault_token=_PROD_TOKEN,
        secrets={**_BASE_SECRETS, "llm_api_key": _PLACEHOLDER_LLM},
    )
    assert settings.secret("llm_api_key") == _PLACEHOLDER_LLM
