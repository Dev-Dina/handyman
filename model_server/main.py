from fastapi import FastAPI
from fastapi import HTTPException, status

from model_server.classifier import ClassifierUnavailableError, get_classifier
from model_server.schemas import ClassifyRequest, ClassifyResponse

app = FastAPI(title="Model Server")


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}


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
