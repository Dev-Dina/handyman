import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infra.logging import get_logger, request_id_var

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = str(uuid.uuid4())
        token = request_id_var.set(req_id)
        request.state.request_id = req_id

        logger.info(
            "request.start",
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("request.error", exc=str(exc))
            raise
        finally:
            request_id_var.reset(token)

        logger.info(
            "request.end",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        response.headers["X-Request-Id"] = req_id
        return response
