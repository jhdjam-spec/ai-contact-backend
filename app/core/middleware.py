"""HTTP-middleware: сквозной request_id и логирование каждого запроса.

Выполняет требование ТЗ «логирование всех запросов в файл»: каждый
запрос/ответ пишется в structlog (а значит и в logs/app.jsonl) с методом,
путём, статусом, длительностью и request_id.
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.core.logging import get_logger

logger = get_logger("http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        clear_contextvars()
        bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        start = time.perf_counter()
        logger.info("request_started")
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request_finished",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
