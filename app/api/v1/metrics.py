"""Роутер метрик: GET /api/metrics.

Агрегированная статистика обращений из БД: всего, по статусам, тональности,
категориям и приоритетам. Полезно для дашборда владельца сайта.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import RepoDep

router = APIRouter(tags=["system"])


@router.get("/metrics", summary="Статистика обращений")
async def metrics(repo: RepoDep) -> dict:
    return await repo.metrics()
