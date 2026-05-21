# Tests

## Structure

```
tests/
  unit/         Pure function/class tests. No network, no Docker, no external services.
  smoke/        Minimal sanity checks: app imports, route registration, artifact schema.
  integration/  FastAPI endpoint behavior via TestClient with mocked infra (no real Ollama).
  eval/         Golden-set schema and quality gates for classification evaluation.
  build/        Docker Compose and config structural checks. Does NOT run Docker.
  fixtures/     Small reusable test data shared across test categories.
```

## Markers

| Marker        | Description |
|---------------|-------------|
| `unit`        | Pure functions/classes, deterministic, no I/O |
| `smoke`       | Import checks, route registration, schema sanity |
| `integration` | FastAPI TestClient, all external services mocked |
| `eval`        | Golden CSV schema and label quality gates |
| `build`       | Compose/Dockerfile structural checks, no execution |

## Commands

```powershell
# All tests (safe — no Docker, no Ollama, no network)
.\.venv\Scripts\python.exe -m pytest -q

# Collect only (dry run)
.\.venv\Scripts\python.exe -m pytest --collect-only

# By category
.\.venv\Scripts\python.exe -m pytest tests/unit
.\.venv\Scripts\python.exe -m pytest tests/smoke
.\.venv\Scripts\python.exe -m pytest tests/integration
.\.venv\Scripts\python.exe -m pytest tests/eval
.\.venv\Scripts\python.exe -m pytest tests/build

# By marker
.\.venv\Scripts\python.exe -m pytest -m unit
.\.venv\Scripts\python.exe -m pytest -m "not build"
```

## Rules

- `unit` and `smoke` must never import or call real Vault, Ollama, Docker, or any network service.
- `integration` tests use `fastapi.testclient.TestClient` and mock all external calls.
- `build` tests parse config files only — never run `docker` commands.
- Tests that require real Ollama, Vault, or Docker must be marked `@pytest.mark.skip` or `@pytest.mark.xfail` with a reason.
- Do not add training, data-fetch, or model-inference logic to any test file.
