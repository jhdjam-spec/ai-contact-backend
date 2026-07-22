"""Фикстуры pytest.

Тесты изолированы от прод-инфраструктуры:
  • БД — SQLite in-memory (aiosqlite), схема создаётся из метаданных моделей;
  • AI — по умолчанию mock (rule-based), сеть не нужна;
  • email — console-бэкенд пишет в temp, реальная почта не трогается.

Настройки окружения задаются ДО импорта app, чтобы get_settings() прочитал их.
"""

from __future__ import annotations

import os

# Настройки для тестового окружения — строго до импорта приложения.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("EMAIL_BACKEND", "console")
os.environ.setdefault("RATE_LIMIT_CONTACT", "1000/minute")  # чтобы не мешал обычным тестам
os.environ.setdefault("CORS_ORIGINS", "*")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import contact  # noqa: E402,F401  (регистрация таблиц)


@pytest_asyncio.fixture
async def db_sessionmaker():
    """Свежая in-memory БД на каждый тест."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_sessionmaker):
    """HTTP-клиент поверх ASGI-приложения с подменённой сессией БД."""

    async def _override_get_session():
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    # Фоновая обработка использует свой sessionmaker — подменяем и его,
    # чтобы фон писал в ту же in-memory БД.
    import app.db.session as session_module
    import app.services.contact_service as cs_module

    session_module._sessionmaker = db_sessionmaker
    cs_module.get_sessionmaker = lambda: db_sessionmaker  # type: ignore

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def valid_payload() -> dict:
    return {
        "name": "Иван Петров",
        "email": "ivan@example.com",
        "phone": "+7 900 123-45-67",
        "comment": "Здравствуйте! Хотим предложить вам проект по разработке.",
    }
