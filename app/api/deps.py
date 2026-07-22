"""Зависимости FastAPI (Dependency Injection).

Собирает граф зависимостей запроса: сессия БД → репозиторий → сервис.
Благодаря этому роутеры не создают объекты руками, а тесты легко подменяют
любой слой через app.dependency_overrides.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.contact_repo import ContactRepository
from app.services.contact_service import ContactService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_contact_repository(session: SessionDep) -> ContactRepository:
    return ContactRepository(session)


RepoDep = Annotated[ContactRepository, Depends(get_contact_repository)]


def get_contact_service(repo: RepoDep) -> ContactService:
    return ContactService(repo)


ContactServiceDep = Annotated[ContactService, Depends(get_contact_service)]
