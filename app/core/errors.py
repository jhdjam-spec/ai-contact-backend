"""Доменные исключения и глобальные обработчики ошибок.

Все ответы об ошибках имеют единый JSON-конверт:

    {"error": {"code": "...", "message": "...", "details": [...]},
     "request_id": "..."}

Это делает контракт API предсказуемым для фронтенда и упрощает отладку:
по request_id ошибку из ответа можно найти в логах.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger("errors")


class AppError(Exception):
    """Базовое доменное исключение приложения."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Внутренняя ошибка сервиса"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[Any] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details or []


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"
    message = "Некорректные входные данные"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Слишком много запросов, попробуйте позже"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Ресурс не найден"


class ExternalServiceError(AppError):
    """Сбой внешней зависимости (AI, SMTP). Обычно перехватывается fallback'ом
    и не доходит до пользователя, но на случай непойманного — 502."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_error"
    message = "Ошибка внешнего сервиса"


def _envelope(request: Request, code: str, message: str, details: list[Any]) -> dict[str, Any]:
    return {
        "error": {"code": code, "message": message, "details": details},
        "request_id": getattr(request.state, "request_id", None),
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Регистрирует глобальные обработчики. Вызывается один раз при старте."""

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "app_error",
            code=exc.code,
            status_code=exc.status_code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "reason": e["msg"]}
            for e in exc.errors()
        ]
        logger.info("validation_error", details=details)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                request, "validation_error", "Некорректные входные данные", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, "http_error", str(exc.detail), []),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Последний рубеж: ничего не утекает наружу, но всё пишется в лог.
        logger.error("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                request, "internal_error", "Внутренняя ошибка сервиса", []
            ),
        )
