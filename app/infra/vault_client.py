import hvac
import requests
from hvac.exceptions import VaultError

from app.domain.errors import SecretNotFoundError, VaultUnavailableError

_MOUNT = "secret"
_PATH = "handyman"


class VaultClient:
    def __init__(self, addr: str, token: str) -> None:
        self._client = hvac.Client(url=addr, token=token)
        try:
            authenticated = self._client.is_authenticated()
        except (VaultError, requests.exceptions.RequestException) as exc:
            raise VaultUnavailableError(f"Vault unreachable at {addr}: {exc}") from exc
        if not authenticated:
            raise VaultUnavailableError(
                f"Vault token rejected at {addr}. Check VAULT_DEV_ROOT_TOKEN."
            )

    def get_secret(self, key: str) -> str:
        return self.get_secret_from_path(_PATH, key)

    def get_secret_from_path(self, path: str, key: str) -> str:
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=_MOUNT,
                path=path,
            )
        except (VaultError, requests.exceptions.RequestException) as exc:
            raise VaultUnavailableError(
                f"Vault error reading {_MOUNT}/{path}: {exc}"
            ) from exc

        data: dict = response.get("data", {}).get("data", {})
        if key not in data:
            raise SecretNotFoundError(f"Secret '{key}' not found at {_MOUNT}/{path}")
        return data[key]
