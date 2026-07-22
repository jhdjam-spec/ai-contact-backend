"""Email-сервис: отправка двух писем (владельцу + копия пользователю).

Паттерн Strategy, как и у AI (см. ADR-0005):
  - ConsoleEmailSender (дефолт) — пишет письма в лог и в файлы logs/emails/*.eml.
    Позволяет проверяющему увидеть ФАКТ отправки двух писем без настройки SMTP.
  - SMTPEmailSender — реальная отправка через aiosmtplib (EMAIL_BACKEND=smtp).

Отправка вызывается из фоновой задачи, поэтому HTTP-ответ пользователю не ждёт
почтовый сервер.
"""

from __future__ import annotations

import abc
import asyncio
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIResult, ContactCreate

logger = get_logger("email")


def _build_owner_email(
    settings: Settings, contact: ContactCreate, ai: AIResult, contact_id: int
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = settings.email_owner
    msg["Subject"] = f"[Обращение #{contact_id}] {ai.category.value} / {ai.priority.value}"
    msg.set_content(
        f"Новое обращение с формы обратной связи.\n\n"
        f"ID: {contact_id}\n"
        f"Имя: {contact.name}\n"
        f"Email: {contact.email}\n"
        f"Телефон: {contact.phone}\n\n"
        f"Комментарий:\n{contact.comment}\n\n"
        f"--- AI-анализ ({ai.provider}) ---\n"
        f"Тональность: {ai.sentiment.value}\n"
        f"Категория: {ai.category.value}\n"
        f"Приоритет: {ai.priority.value}\n\n"
        f"Черновик ответа:\n{ai.suggested_reply}\n"
    )
    return msg


def _build_user_email(
    settings: Settings, contact: ContactCreate, ai: AIResult
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = str(contact.email)
    msg["Subject"] = "Ваше обращение получено"
    msg.set_content(
        f"Здравствуйте, {contact.name}!\n\n"
        f"Спасибо за обращение — оно получено и будет рассмотрено в ближайшее время.\n\n"
        f"Ваше сообщение:\n{contact.comment}\n\n"
        f"С уважением,\nкоманда сайта"
    )
    return msg


class EmailSender(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender(EmailSender):
    """Пишет письмо в лог и сохраняет .eml в logs/emails/. Без реальной отправки."""

    name = "console"

    def __init__(self, out_dir: str = "logs/emails") -> None:
        self._dir = Path(out_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    async def send(self, message: EmailMessage) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        to = message["To"].replace("@", "_at_").replace("/", "_")
        path = self._dir / f"{ts}__{to}.eml"
        path.write_text(message.as_string(), encoding="utf-8")
        logger.info(
            "email_sent_console",
            to=message["To"],
            subject=message["Subject"],
            file=str(path),
        )


class SMTPEmailSender(EmailSender):
    """Реальная отправка через SMTP (aiosmtplib). Требует SMTP_* в .env."""

    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send(self, message: EmailMessage) -> None:
        import aiosmtplib

        s = self._settings
        await aiosmtplib.send(
            message,
            hostname=s.smtp_host,
            port=s.smtp_port,
            username=s.smtp_user,
            password=s.smtp_password,
            start_tls=s.smtp_tls,
            timeout=15,
        )
        logger.info("email_sent_smtp", to=message["To"], subject=message["Subject"])


def _build_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp" and settings.smtp_host:
        return SMTPEmailSender(settings)
    return ConsoleEmailSender()


class EmailService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._sender = _build_sender(self._settings)

    @property
    def backend_name(self) -> str:
        return self._sender.name

    async def send_notifications(
        self, *, contact: ContactCreate, ai: AIResult, contact_id: int
    ) -> None:
        """Отправляет оба письма. Ошибка одного письма не отменяет второе —
        каждое отправляется независимо, сбои логируются."""
        owner = _build_owner_email(self._settings, contact, ai, contact_id)
        user = _build_user_email(self._settings, contact, ai)

        results = await asyncio.gather(
            self._safe_send(owner, "owner"),
            self._safe_send(user, "user"),
            return_exceptions=False,
        )
        logger.info("emails_dispatched", sent=sum(results), total=2)

    async def _safe_send(self, message: EmailMessage, kind: str) -> int:
        try:
            await self._sender.send(message)
            return 1
        except Exception as exc:  # noqa: BLE001 — письмо не должно ронять поток
            logger.error("email_send_failed", kind=kind, error=str(exc))
            return 0


_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
