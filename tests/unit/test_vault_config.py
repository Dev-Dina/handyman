from unittest.mock import MagicMock, patch

import pytest
import requests

from app.domain.errors import SecretNotFoundError, VaultUnavailableError
from app.infra.vault_client import VaultClient

pytestmark = pytest.mark.unit


def _make_client(is_authenticated=True, kv_data: dict | None = None):
    mock_hvac = MagicMock()
    mock_hvac.is_authenticated.return_value = is_authenticated
    if kv_data is not None:
        mock_hvac.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": kv_data}
        }
    return mock_hvac


def test_vault_unreachable_raises():
    with patch("app.infra.vault_client.hvac.Client") as mock_class:
        mock_class.return_value.is_authenticated.side_effect = (
            requests.exceptions.ConnectionError("refused")
        )
        with pytest.raises(VaultUnavailableError, match="unreachable"):
            VaultClient(addr="http://localhost:9999", token="bad")


def test_vault_bad_token_raises():
    with patch("app.infra.vault_client.hvac.Client") as mock_class:
        mock_class.return_value = _make_client(is_authenticated=False)
        with pytest.raises(VaultUnavailableError, match="token rejected"):
            VaultClient(addr="http://localhost:8200", token="wrong")


def test_missing_secret_raises():
    with patch("app.infra.vault_client.hvac.Client") as mock_class:
        mock_class.return_value = _make_client(kv_data={})
        client = VaultClient(addr="http://localhost:8200", token="dev-root-token")
        with pytest.raises(SecretNotFoundError, match="jwt_signing_key"):
            client.get_secret("jwt_signing_key")


def test_get_secret_returns_value():
    with patch("app.infra.vault_client.hvac.Client") as mock_class:
        mock_class.return_value = _make_client(
            kv_data={"jwt_signing_key": "test-value"}
        )
        client = VaultClient(addr="http://localhost:8200", token="dev-root-token")
        assert client.get_secret("jwt_signing_key") == "test-value"
