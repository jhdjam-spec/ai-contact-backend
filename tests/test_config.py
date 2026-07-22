"""Тесты нормализации настроек."""

from __future__ import annotations

from app.core.config import Settings


def test_postgres_url_normalized_to_asyncpg():
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_postgresql_url_gets_async_driver():
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.database_url == "postgresql+asyncpg://u:p@host:5432/db"


def test_asyncpg_url_untouched():
    url = "postgresql+asyncpg://u:p@host:5432/db"
    assert Settings(database_url=url).database_url == url


def test_sqlite_url_untouched():
    url = "sqlite+aiosqlite:///:memory:"
    assert Settings(database_url=url).database_url == url


def test_cors_wildcard():
    assert Settings(cors_origins="*").cors_origins_list == ["*"]


def test_cors_list_parsed():
    s = Settings(cors_origins="https://a.com, https://b.com")
    assert s.cors_origins_list == ["https://a.com", "https://b.com"]
