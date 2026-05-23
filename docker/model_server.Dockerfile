FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" scikit-learn joblib

# E5 embedding stack for the /embed endpoint (RAG dense/hybrid). Torch + transformers
# live ONLY in this image — never in the API image. CPU-only torch wheel keeps size down.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch
RUN pip install --no-cache-dir transformers numpy

# Run fully offline at runtime — the E5 weights are shipped in the image (below),
# so no HuggingFace hub network call is needed.
ENV TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1

WORKDIR /app

COPY model_server/ ./model_server/
COPY artifacts/classical/best_model.joblib ./artifacts/classical/best_model.joblib

# Offline-cached E5-small-v2 weights (config.json + model.safetensors + tokenizer).
# Loaded by model_server/embedder.py via EMBED_MODEL_PATH (defaults to this dir).
COPY artifacts/embeddings/e5-small-v2/ ./artifacts/embeddings/e5-small-v2/

CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8001"]
