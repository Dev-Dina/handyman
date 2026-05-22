FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" scikit-learn joblib

WORKDIR /app

COPY model_server/ ./model_server/
COPY artifacts/classical/best_model.joblib ./artifacts/classical/best_model.joblib

CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8001"]
