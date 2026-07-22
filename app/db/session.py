"""Async-подключение к БД: engine, sessionmaker и зависимость сессии.

Используется asyncpg-драйвер (postgresql+asyncpg). Для тестов URL можно
подменить на sqlite+aiosqlite. Сессия отдаётся как async-генератор, что
позволяет FastAPI закрывать её после запроса.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,  # отсекает «протухшие» соединения
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI-зависимость: одна сессия на запрос, commit/rollback — в вызывающем
    коде (репозитории/сервисе)."""
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


async def dispose_engine() -> None:
    """Закрыть пул соединений при остановке приложения."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
