"""ORM-модель обращения из формы обратной связи."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class Category(StrEnum):
    JOB_OFFER = "job_offer"        # предложение о работе / вакансия
    PROJECT = "project"            # заказ проекта / сотрудничество
    QUESTION = "question"          # вопрос по стеку/опыту
    SPAM = "spam"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProcessingStatus(StrEnum):
    RECEIVED = "received"        # принято, ждёт фоновой обработки
    PROCESSED = "processed"      # AI отработал, письма отправлены
    FAILED = "failed"            # фоновая обработка упала (см. логи)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Данные из формы ---
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text)

    # --- Результат AI-анализа (заполняется в фоне) ---
    sentiment: Mapped[Sentiment] = mapped_column(
        Enum(Sentiment, native_enum=False, length=16), default=Sentiment.UNKNOWN
    )
    category: Mapped[Category] = mapped_column(
        Enum(Category, native_enum=False, length=16), default=Category.OTHER
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=16), default=Priority.MEDIUM
    )
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- Служебное ---
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False, length=16),
        default=ProcessingStatus.RECEIVED,
        index=True,
    )
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contact id={self.id} email={self.email!r} status={self.status.value}>"
