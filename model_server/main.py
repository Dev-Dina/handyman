from fastapi import FastAPI
from fastapi import HTTPException, status

from model_server.classifier import ClassifierUnavailableError, get_classifier
from model_server.config import EMBED_DIMENSION, EMBED_MODEL_NAME
from model_server.embedder import EmbedderUnavailableError, embed_texts
from model_server.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    EmbedRequest,
    EmbedResponse,
)

app = FastAPI(title="Model Server")


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/embed", response_model=EmbedResponse)
async def embed(payload: EmbedRequest) -> EmbedResponse:
    try:
        vectors = embed_texts(payload.texts)
    except EmbedderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "embedder_unavailable", "message": str(exc)},
        ) from exc
    dimension = len(vectors[0]) if vectors else EMBED_DIMENSION
    return EmbedResponse(
        embeddings=vectors, model=EMBED_MODEL_NAME, dimension=dimension
    )


@app.post("/classify", response_model=ClassifyResponse)
async def classify_issue(payload: ClassifyRequest) -> ClassifyResponse:
    try:
        classifier = get_classifier()
        return classifier.classify(title=payload.title, body=payload.body)
    except ClassifierUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "classifier_unavailable", "message": str(exc)},
        ) from exc
