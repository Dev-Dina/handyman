from fastapi import FastAPI

app = FastAPI(title="Model Server")


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}
