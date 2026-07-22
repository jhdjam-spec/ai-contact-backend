"""Contact-сервис: оркестрация полного цикла обработки обращения.

Здесь живёт бизнес-логика верхнего уровня — то, что ТЗ называет
«запрос → валидация → бизнес-логика → AI → отправка → ответ».

Разделение на две фазы ради быстрого ответа пользователю:
  • submit()          — синхронно: сохранить обращение, вернуть id (202).
  • process_in_background() — асинхронно (BackgroundTasks): AI-анализ,
    сохранение результата, отправка двух писем, обновление статуса.

Фоновая фаза создаёт собственную сессию БД, т.к. request-scoped сессия к
моменту её выполнения уже закрыта.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.contact import Contact, ProcessingStatus
from app.repositories.contact_repo import ContactRepository
from app.schemas.contact import ContactCreate
from app.services.ai_service import AIService, get_ai_service
from app.services.email_service import EmailService, get_email_service

logger = get_logger("contact.service")


class ContactService:
    def __init__(
        self,
        repo: ContactRepository,
        ai_service: AIService | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        self._repo = repo
        self._ai = ai_service or get_ai_service()
        self._email = email_service or get_email_service()

    async def submit(
        self, data: ContactCreate, *, client_ip: str | None, request_id: str | None
    ) -> Contact:
        """Фаза 1: принять и сохранить обращение. Быстро, без внешних вызовов."""
        contact = await self._repo.create(
            data, client_ip=client_ip, request_id=request_id
        )
        logger.info("contact_received", contact_id=contact.id, email=contact.email)
        return contact


async def process_in_background(contact_id: int, data: ContactCreate) -> None:
    """Фаза 2: тяжёлая обработка вне HTTP-запроса.

    Отдельная функция (а не метод), чтобы FastAPI BackgroundTasks мог вызвать её
    с чистой, независимой сессией БД. Любой сбой переводит обращение в статус
    FAILED и логируется, но не влияет на уже отданный ответ 202.
    """
    ai = get_ai_service()
    email = get_email_service()
    maker = get_sessionmaker()

    async with maker() as session:
        repo = ContactRepository(session)
        try:
            result = await ai.analyze(name=data.name, comment=data.comment)
            await repo.apply_ai_result(contact_id, result)
            logger.info(
                "contact_analyzed",
                contact_id=contact_id,
                provider=result.provider,
                sentiment=result.sentiment.value,
                category=result.category.value,
                priority=result.priority.value,
            )

            await email.send_notifications(
                contact=data, ai=result, contact_id=contact_id
            )
            await repo.set_status(contact_id, ProcessingStatus.PROCESSED)
            logger.info("contact_processed", contact_id=contact_id)
        except Exception as exc:  # noqa: BLE001 — фон не должен падать «наверх»
            logger.error(
                "contact_processing_failed", contact_id=contact_id, error=str(exc)
            )
            await repo.set_status(contact_id, ProcessingStatus.FAILED)
