"""Repository-слой: вся работа с БД для обращений.

Инкапсулирует SQLAlchemy так, что сервисы не знают про ORM и запросы.
Это граница слоёв: сервис оперирует доменными объектами и параметрами,
а не select()/session.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact, ProcessingStatus
from app.schemas.contact import AIResult, ContactCreate


class ContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: ContactCreate,
        *,
        client_ip: str | None,
        request_id: str | None,
    ) -> Contact:
        contact = Contact(
            name=data.name,
            email=str(data.email),
            phone=data.phone,
            comment=data.comment,
            client_ip=client_ip,
            request_id=request_id,
            status=ProcessingStatus.RECEIVED,
        )
        self._session.add(contact)
        await self._session.commit()
        await self._session.refresh(contact)
        return contact

    async def get(self, contact_id: int) -> Contact | None:
        return await self._session.get(Contact, contact_id)

    async def apply_ai_result(self, contact_id: int, result: AIResult) -> None:
        contact = await self._session.get(Contact, contact_id)
        if contact is None:
            return
        contact.sentiment = result.sentiment
        contact.category = result.category
        contact.priority = result.priority
        contact.suggested_reply = result.suggested_reply
        contact.ai_provider = result.provider
        await self._session.commit()

    async def set_status(self, contact_id: int, status: ProcessingStatus) -> None:
        contact = await self._session.get(Contact, contact_id)
        if contact is None:
            return
        contact.status = status
        await self._session.commit()

    # --- Агрегаты для GET /api/metrics ---

    async def count_total(self) -> int:
        result = await self._session.scalar(select(func.count()).select_from(Contact))
        return int(result or 0)

    async def count_by_enum(self, column) -> dict[str, int]:
        rows = await self._session.execute(
            select(column, func.count()).group_by(column)
        )
        out: dict[str, int] = {}
        for value, count in rows.all():
            key = value.value if hasattr(value, "value") else str(value)
            out[key] = int(count)
        return out

    async def metrics(self) -> dict[str, object]:
        return {
            "total": await self.count_total(),
            "by_status": await self.count_by_enum(Contact.status),
            "by_sentiment": await self.count_by_enum(Contact.sentiment),
            "by_category": await self.count_by_enum(Contact.category),
            "by_priority": await self.count_by_enum(Contact.priority),
        }
