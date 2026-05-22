"""Build tests: docker-compose.yml structural checks. No Docker execution."""

from __future__ import annotations

import pytest

from app.core.paths import PROJECT_ROOT

pytestmark = pytest.mark.build

_COMPOSE_FILE = PROJECT_ROOT / "docker-compose.yml"

_REQUIRED_SERVICES = {
    "db",
    "redis",
    "vault",
    "vault-init",
    "migrate",
    "api",
    "model_server",
}
_REQUIRED_VOLUMES = {"db_data", "minio_data"}


def _load_compose() -> dict:
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not installed — skipping compose parse tests")
    with open(_COMPOSE_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_compose_file_exists():
    assert _COMPOSE_FILE.exists(), f"Missing: {_COMPOSE_FILE}"


def test_compose_has_services():
    data = _load_compose()
    assert "services" in data, "docker-compose.yml missing 'services' key"


def test_required_services_present():
    data = _load_compose()
    services = set(data.get("services", {}).keys())
    missing = _REQUIRED_SERVICES - services
    assert not missing, f"Missing services: {missing}"


def test_api_service_has_healthcheck():
    data = _load_compose()
    api = data["services"].get("api", {})
    assert "healthcheck" in api, "api service missing healthcheck"


def test_db_service_has_healthcheck():
    data = _load_compose()
    db = data["services"].get("db", {})
    assert "healthcheck" in db, "db service missing healthcheck"


def test_vault_service_has_healthcheck():
    data = _load_compose()
    vault = data["services"].get("vault", {})
    assert "healthcheck" in vault, "vault service missing healthcheck"


def test_api_depends_on_vault_init():
    data = _load_compose()
    api = data["services"].get("api", {})
    depends = api.get("depends_on", {})
    assert "vault-init" in depends, "api service should depend on vault-init"


def test_required_volumes_declared():
    data = _load_compose()
    volumes = set((data.get("volumes") or {}).keys())
    missing = _REQUIRED_VOLUMES - volumes
    assert not missing, f"Missing top-level volumes: {missing}"


def test_no_host_mode_networking():
    data = _load_compose()
    for name, svc in (data.get("services") or {}).items():
        net_mode = svc.get("network_mode", "")
        assert net_mode != "host", f"Service '{name}' uses host network mode"


def test_db_uses_pgvector_image():
    """db service must use a pgvector-enabled image so migration 004 can run."""
    data = _load_compose()
    db_image = data["services"]["db"]["image"]
    assert "pgvector" in db_image, (
        f"db image '{db_image}' does not include pgvector — "
        "migration 004 requires CREATE EXTENSION vector"
    )
