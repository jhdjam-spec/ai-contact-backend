"""Declarative base для ORM-моделей SQLAlchemy 2.0."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Общий базовый класс всех моделей. Alembic находит таблицы через
    Base.metadata."""
