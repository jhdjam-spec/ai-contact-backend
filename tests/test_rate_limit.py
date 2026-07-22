"""Тест rate limiting.

Лимит задаётся на уровне декоратора из настройки RATE_LIMIT_CONTACT. В общем
conftest он намеренно высокий (1000/minute), чтобы не мешать остальным тестам,
поэтому здесь мы напрямую дёргаем лимитер slowapi и проверяем его срабатывание
на низком пороге, не завязываясь на глобальный лимит эндпоинта.
"""

from __future__ import annotations

from app.core.rate_limit import _client_key


async def test_limiter_blocks_after_limit():
    # Эмулируем 3 запроса при лимите 2/minute для одного ключа —
    # проверяем механику библиотеки limits, на которой построен slowapi.
    from limits import parse
    from limits.aio.storage import MemoryStorage
    from limits.aio.strategies import FixedWindowRateLimiter

    storage = MemoryStorage()
    strategy = FixedWindowRateLimiter(storage)
    item = parse("2/minute")

    key = "test-client"
    assert await strategy.hit(item, key) is True   # 1
    assert await strategy.hit(item, key) is True   # 2
    assert await strategy.hit(item, key) is False  # 3 — заблокирован


def test_client_key_prefers_forwarded_for():
    """За прокси (Render) ключ берётся из X-Forwarded-For."""

    class _Req:
        headers = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
        client = type("C", (), {"host": "10.0.0.1"})()

    assert _client_key(_Req()) == "203.0.113.7"
