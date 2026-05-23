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

# Runtime prompt files — chat orchestrator loads prompts/chat_system.md at first call.
COPY prompts/ ./prompts/

# RAG runtime corpus — only the deployed chunk file is copied.
# raw/, processed/, experiments/ are excluded by .dockerignore.
COPY data/rag/chunks/chunks_section_aware.jsonl ./data/rag/chunks/chunks_section_aware.jsonl

# RAG live hybrid: shipped E5 chunk embeddings + manifest (small, ~3.3MB).
# The query embedding comes from model_server /embed; no torch in this image.
COPY artifacts/rag/intfloat_e5_small_v2_chunks.npy ./artifacts/rag/intfloat_e5_small_v2_chunks.npy
COPY artifacts/rag/intfloat_e5_small_v2_manifest.json ./artifacts/rag/intfloat_e5_small_v2_manifest.json

# Small, non-secret eval reports served by GET /api/v1/evals/summary so the
# dashboard reads results through the API (re-included via .dockerignore).
COPY reports/rag/api_eval_report.json ./reports/rag/api_eval_report.json
COPY reports/rag/generation_eval_report.json ./reports/rag/generation_eval_report.json
COPY reports/classification_eval_report.json ./reports/classification_eval_report.json

# Install main dependencies only (no [ml] extras — torch must not be present).
# Torch and transformers live behind the model_server boundary only.
RUN uv pip install --system --no-cache .

# Hard assertion: torch must not be installed in the API image.
RUN python -c "import importlib.util; assert importlib.util.find_spec('torch') is None, 'torch found in API image — remove it'"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
