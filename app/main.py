import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.middleware import RequestContextMiddleware
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.memory import router as memory_router
from app.api.routes.rag import router as rag_router
from app.api.routes.widgets import router as widgets_router
from app.api.routes.tools import router as tools_router
from app.domain.errors import VaultUnavailableError
from app.infra.logging import configure_logging, get_logger
from app.infra.tracing import configure_tracing

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
    configure_tracing()

    from app.core.config import get_settings

    try:
        get_settings()
    except VaultUnavailableError as exc:
        raise RuntimeError(f"Startup aborted — Vault is not ready: {exc}") from exc

    logger.info("app.started")
    yield
    logger.info("app.stopped")


app = FastAPI(title="Maintainer's Copilot API", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(memory_router)
app.include_router(widgets_router)


@app.get("/healthz")
async def health() -> dict:
    return {"status": "ok"}
