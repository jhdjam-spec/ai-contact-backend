"""Роутер формы обратной связи: POST /api/contact.

Тонкий слой: принимает валидированное тело, передаёт в сервис, ставит фоновую
задачу на AI+email и возвращает 202 Accepted. Никакой бизнес-логики здесь нет.

ВАЖНО: здесь НЕ используем `from __future__ import annotations`. Под декоратором
`@limiter.limit` (slowapi оборачивает функцию через functools.wraps) FastAPI не
может разрезолвить отложенные строковые аннотации параметров-зависимостей, и все
они деградируют до обязательных полей тела → каждый валидный запрос падает с 422
(«payload/background_tasks/service — Field required»). С реальными аннотациями
(объектами, а не строками) резолвинг работает корректно.
"""

from fastapi import APIRouter, BackgroundTasks, Request, status

from app.api.deps import ContactServiceDep
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.schemas.contact import ContactAccepted, ContactCreate
from app.services.contact_service import process_in_background

router = APIRouter(tags=["contact"])


@router.post(
    "/contact",
    response_model=ContactAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Отправить обращение с формы обратной связи",
    responses={
        202: {"description": "Обращение принято, обрабатывается в фоне"},
        422: {"description": "Ошибка валидации входных данных"},
        429: {"description": "Превышен лимит запросов (rate limit)"},
    },
)
@limiter.limit(get_settings().rate_limit_contact)
async def create_contact(
    request: Request,
    payload: ContactCreate,
    background_tasks: BackgroundTasks,
    service: ContactServiceDep,
) -> ContactAccepted:
    client_ip = request.client.host if request.client else None
    request_id = getattr(request.state, "request_id", None)

    contact = await service.submit(
        payload, client_ip=client_ip, request_id=request_id
    )

    # AI-анализ и рассылка писем — в фоне, чтобы ответ был мгновенным.
    background_tasks.add_task(process_in_background, contact.id, payload)

    return ContactAccepted(id=contact.id, status=contact.status)
