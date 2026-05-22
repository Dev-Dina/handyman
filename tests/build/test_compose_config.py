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


def test_vite_config_base_matches_nginx_path():
    """Vite base must be '/widget-app/' to match nginx serving path and loader URL."""
    vite_config = (PROJECT_ROOT / "widget" / "vite.config.ts").read_text()
    assert (
        "base: '/widget-app/'" in vite_config or 'base: "/widget-app/"' in vite_config
    ), (
        "widget/vite.config.ts must set base='/widget-app/' — "
        "nginx serves dist/ under /widget-app/ and the loader defaults to that path"
    )


def test_nginx_widget_conf_exists():
    """docker/nginx-widget.conf must exist — widget.Dockerfile copies it."""
    assert (PROJECT_ROOT / "docker" / "nginx-widget.conf").exists(), (
        "docker/nginx-widget.conf missing — widget.Dockerfile requires it"
    )


def test_chatbot_dockerfile_has_pythonpath():
    """chatbot.Dockerfile must set PYTHONPATH=/app for chatbot package imports."""
    chatbot_df = (PROJECT_ROOT / "docker" / "chatbot.Dockerfile").read_text()
    assert "PYTHONPATH=/app" in chatbot_df, (
        "docker/chatbot.Dockerfile must set ENV PYTHONPATH=/app — "
        "streamlit does not add WORKDIR to sys.path"
    )


def test_api_dockerfile_copies_rag_corpus():
    """API Dockerfile must COPY the RAG chunk corpus — retrieval.py loads it at runtime."""
    api_df = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "chunks_section_aware.jsonl" in api_df, (
        "Dockerfile must COPY data/rag/chunks/chunks_section_aware.jsonl — "
        "app/services/rag/retrieval.py raises RagCorpusNotReadyError without it"
    )


def test_rag_corpus_file_exists_locally():
    """The RAG chunk corpus must exist locally so docker compose build api can copy it."""
    corpus = PROJECT_ROOT / "data" / "rag" / "chunks" / "chunks_section_aware.jsonl"
    assert corpus.exists(), (
        f"RAG corpus missing at {corpus} — run the RAG pipeline to generate it"
    )


def test_dockerignore_does_not_block_rag_corpus():
    """.dockerignore must not exclude data/rag/chunks/chunks_section_aware.jsonl."""
    dockerignore = PROJECT_ROOT / ".dockerignore"
    if not dockerignore.exists():
        return  # No .dockerignore — all files in context by default
    lines = [
        ln.strip()
        for ln in dockerignore.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    # If data/ is excluded wholesale, negation rules must re-include the rag corpus.
    data_excluded = any(ln in ("data/", "data") for ln in lines)
    if data_excluded:
        has_exception = any(ln.startswith("!") and "data/rag" in ln for ln in lines)
        assert has_exception, (
            ".dockerignore excludes data/ but must add '!data/rag/...' exception "
            "so chunks_section_aware.jsonl reaches the API image"
        )


def test_api_service_has_redis_url():
    """api service must set REDIS_URL so the write_memory tool reaches Redis by service name."""
    data = _load_compose()
    api_env = data["services"].get("api", {}).get("environment", {})
    assert "REDIS_URL" in api_env, (
        "api service must set REDIS_URL=redis://redis:6379/0 — "
        "app/infra/redis_client.py defaults to localhost which is unreachable inside Docker"
    )
    redis_url = api_env["REDIS_URL"]
    assert "redis" in str(redis_url) and "localhost" not in str(redis_url), (
        f"REDIS_URL '{redis_url}' must use service name 'redis', not 'localhost'"
    )


def test_api_service_has_cors_origins():
    """api service must set CORS_ALLOWED_ORIGINS so the widget React app can call the API."""
    data = _load_compose()
    api_env = data["services"].get("api", {}).get("environment", {})
    assert "CORS_ALLOWED_ORIGINS" in api_env, (
        "api service must set CORS_ALLOWED_ORIGINS — "
        "the widget (port 3000) makes cross-origin fetch requests to the API (port 8000)"
    )
    cors_val = str(api_env["CORS_ALLOWED_ORIGINS"])
    assert "localhost:3000" in cors_val, (
        f"CORS_ALLOWED_ORIGINS '{cors_val}' must include http://localhost:3000 (widget nginx)"
    )


def test_api_dockerfile_copies_prompts():
    """API Dockerfile must COPY prompts/ — chat orchestrator loads chat_system.md at runtime."""
    api_df = (PROJECT_ROOT / "Dockerfile").read_text()
    assert "prompts" in api_df, (
        "Dockerfile must COPY prompts/ — "
        "app/services/chat/prompts.py raises FileNotFoundError without chat_system.md"
    )


def test_chat_system_prompt_exists_locally():
    """prompts/chat_system.md must exist locally so docker compose build api can copy it."""
    prompt = PROJECT_ROOT / "prompts" / "chat_system.md"
    assert prompt.exists(), f"prompts/chat_system.md missing at {prompt}"


def test_dockerignore_does_not_block_prompts():
    """.dockerignore must not exclude prompts/chat_system.md."""
    dockerignore = PROJECT_ROOT / ".dockerignore"
    if not dockerignore.exists():
        return  # No .dockerignore — all files in context by default
    lines = [
        ln.strip()
        for ln in dockerignore.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    prompts_excluded = any(ln in ("prompts/", "prompts") for ln in lines)
    if prompts_excluded:
        has_exception = any(ln.startswith("!") and "prompts" in ln for ln in lines)
        assert has_exception, (
            ".dockerignore excludes prompts/ but must add '!prompts/...' exception "
            "so chat_system.md reaches the API image"
        )
