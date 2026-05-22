FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Install main dependencies only (no [ml] extras — torch must not be present).
# Torch and transformers live behind the model_server boundary only.
RUN uv pip install --system --no-cache .

# Hard assertion: torch must not be installed in the API image.
RUN python -c "import importlib.util; assert importlib.util.find_spec('torch') is None, 'torch found in API image — remove it'"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
