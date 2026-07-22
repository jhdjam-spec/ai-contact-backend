"""Pydantic-схемы формы обратной связи (входные и выходные контракты API).

Валидация — первый рубеж безопасности: имя/комментарий очищаются от лишних
пробелов и управляющих символов, телефон нормализуется в формат E.164 через
библиотеку phonenumbers, email проверяется email-validator (через EmailStr).
"""

from __future__ import annotations

import re
from datetime import datetime

import phonenumbers
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.contact import Category, Priority, ProcessingStatus, Sentiment

# Управляющие символы (кроме перевода строки/таба) — вырезаем из текста.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_text(value: str) -> str:
    value = _CONTROL_CHARS.sub("", value)
    return value.strip()


class ContactCreate(BaseModel):
    """Тело запроса POST /api/contact."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=2, max_length=120, examples=["Иван Петров"])
    email: EmailStr = Field(..., examples=["ivan@example.com"])
    phone: str = Field(..., min_length=5, max_length=32, examples=["+7 900 123-45-67"])
    comment: str = Field(
        ..., min_length=5, max_length=4000, examples=["Здравствуйте! Хотим предложить проект."]
    )

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = _clean_text(v)
        if len(v) < 2:
            raise ValueError("Имя слишком короткое")
        # Разрешаем буквы (в т.ч. кириллицу), пробелы, дефис, апостроф, точку.
        if not re.fullmatch(r"[^\d<>@/\\{}\[\]]{2,120}", v):
            raise ValueError("Имя содержит недопустимые символы")
        return v

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        v = _clean_text(v)
        try:
            # RU как регион по умолчанию, если номер без "+".
            parsed = phonenumbers.parse(v, "RU")
        except phonenumbers.NumberParseException as exc:
            raise ValueError("Не удалось разобрать номер телефона") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("Некорректный номер телефона")
        # Нормализуем в единый формат E.164: +79001234567
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    @field_validator("comment")
    @classmethod
    def _validate_comment(cls, v: str) -> str:
        v = _clean_text(v)
        if len(v) < 5:
            raise ValueError("Комментарий слишком короткий")
        return v


class AIResult(BaseModel):
    """Результат AI-анализа (общий контракт для всех провайдеров)."""

    sentiment: Sentiment
    category: Category
    priority: Priority
    suggested_reply: str
    provider: str


class ContactAccepted(BaseModel):
    """Ответ 202 Accepted сразу после приёма обращения."""

    id: int
    status: ProcessingStatus
    message: str = "Обращение принято и обрабатывается"


class ContactRead(BaseModel):
    """Полное представление обращения (например для GET по id)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str
    comment: str
    sentiment: Sentiment
    category: Category
    priority: Priority
    suggested_reply: str | None
    ai_provider: str | None
    status: ProcessingStatus
    created_at: datetime
