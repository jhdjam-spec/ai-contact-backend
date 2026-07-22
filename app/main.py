"""Точка входа FastAPI: сборка приложения.

Собирает воедино все слои: настройки → логирование → middleware → CORS →
rate limiting → обработчики ошибок → роутеры. Swagger/OpenAPI генерируется
автоматически и доступен на /docs (Swagger UI) и /redoc.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import contact, health, metrics
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware
from app.core.rate_limit import limiter
from app.db.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger("startup")
    settings = get_settings()
    logger.info(
        "app_starting",
        env=settings.app_env,
        ai_provider=settings.ai_provider,
        email_backend=settings.email_backend,
    )
    yield
    await dispose_engine()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Backend-сервис формы обратной связи для лендинга разработчика.\n\n"
            "Полный цикл: **валидация → сохранение → AI-анализ → email → ответ**. "
            "AI-анализ (тональность, категория, приоритет, черновик ответа) "
            "выполняется с graceful fallback на rule-based провайдер."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # --- Rate limiting (slowapi) ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # --- request_id + логирование запросов ---
    app.add_middleware(RequestContextMiddleware)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # --- Глобальные обработчики ошибок ---
    register_exception_handlers(app)

    # --- Роутеры (общий префикс /api) ---
    app.include_router(contact.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    async def root(request: Request) -> dict:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
