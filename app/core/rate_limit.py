"""Rate limiting на slowapi.

Ключ лимита — IP-адрес клиента (с учётом X-Forwarded-For за прокси/Render).
Хранилище: Redis, если задан REDIS_URL, иначе in-memory — для демо и одного
инстанса этого достаточно. Лимит на эндпоинт задаётся декоратором в роутере.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _client_key(request: Request) -> str:
    """IP клиента с приоритетом первого адреса из X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def build_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=_client_key,
        storage_uri=settings.redis_url or "memory://",
        default_limits=[],
    )


# Единый инстанс лимитера на приложение.
limiter = build_limiter()
