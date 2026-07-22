"""Роутер здоровья сервиса: GET /api/health.

Не просто «200 OK», а реальная проверка зависимостей: доступность БД и текущее
состояние AI-провайдера (не деградирован ли). Возвращает 200, если сервис
способен принимать обращения (БД жива), иначе 503.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.services.ai_service import get_ai_service
from app.services.email_service import get_email_service

router = APIRouter(tags=["system"])


@router.get("/health", summary="Проверка состояния сервиса и зависимостей")
async def health(session: SessionDep, response: Response) -> dict:
    settings = get_settings()

    # Проверка БД простым запросом.
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    ai = get_ai_service()
    email = get_email_service()

    checks = {
        "database": "ok" if db_ok else "down",
        "ai_provider": ai.primary_name,
        "ai_degraded": ai.degraded,
        "email_backend": email.backend_name,
    }

    healthy = db_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "healthy" if healthy else "unhealthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "env": settings.app_env,
        "checks": checks,
    }
