"""Конфигурация приложения на pydantic-settings.

Единственный источник правды по настройкам. Значения читаются из окружения
и файла `.env`; у всех есть дефолты, рассчитанные на запуск демо без секретов.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Приложение ---
    app_name: str = "AI Contact Backend"
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    log_dir: str = "logs"

    # --- CORS ---
    cors_origins: str = "*"

    # --- База данных ---
    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/contacts"

    # --- Rate limiting ---
    rate_limit_contact: str = "5/minute"
    redis_url: str | None = None

    # --- AI ---
    ai_provider: Literal["mock", "anthropic"] = "mock"
    ai_timeout_seconds: float = 10.0
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_base_url: str | None = None

    # --- Email ---
    email_backend: Literal["console", "smtp"] = "console"
    email_owner: str = "owner@example.com"
    email_from: str = "AI Contact <no-reply@example.com>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_tls: bool = True

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Приводим URL к async-драйверу.

        Хостинги (Render, Heroku) выдают `postgres://...`, а SQLAlchemy async
        требует явный драйвер `postgresql+asyncpg://`. Нормализуем автоматически,
        чтобы не ловить грабли при деплое.
        """
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS как список. `*` разворачивается в `["*"]`."""
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Кешированный синглтон настроек (читается один раз на процесс)."""
    return Settings()  # type: ignore[call-arg]
