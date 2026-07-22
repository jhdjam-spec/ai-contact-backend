# ADR-0002: Стек FastAPI + async SQLAlchemy + PostgreSQL

## Status
Accepted
Date: 2026-07-22 · Deciders: @jhdjam-spec

## Context

Нужен backend для формы обратной связи: REST API, валидация, автодокументация,
хранение обращений и их AI-разметки. ТЗ разрешает Python (Django / FastAPI /
Flask) и не требует конкретную БД, но даёт плюс за навыки работы с БД. Пожелание
заказчика: Python + FastAPI + Postgres. Обработка включает внешние вызовы (AI,
SMTP), которые не должны блокировать обработку других запросов.

## Decision Drivers

* Обязательно: async I/O (внешние вызовы AI/SMTP без блокировки event loop).
* Обязательно: строгая валидация входных данных и автогенерация OpenAPI/Swagger.
* Обязательно: работа с реляционной БД + версионирование схемы.
* Желательно: минимум boilerplate, быстрый старт, воспроизводимые зависимости.
* Желательно: тесты без поднятого Postgres.

## Considered Options

### Вариант 1: FastAPI + async SQLAlchemy + PostgreSQL
- Плюсы: async из коробки; Pydantic v2 — валидация; авто-Swagger/ReDoc;
  SQLAlchemy 2.0 async + Alembic; тесты можно гонять на SQLite.
- Минусы: async требует аккуратности с сессиями (запрос vs фон).

### Вариант 2: Flask + SQLAlchemy (sync)
- Плюсы: проще, ниже порог входа.
- Минусы: синхронный — внешние вызовы блокируют воркер; валидация и OpenAPI
  вручную/через расширения.

### Вариант 3: Django + DRF
- Плюсы: «батарейки», admin, ORM, миграции.
- Минусы: избыточен для одного эндпоинта (YAGNI); async-поддержка частичная.

## Decision

Выбрали **Вариант 1: FastAPI + SQLAlchemy 2.0 (async, asyncpg) + PostgreSQL 16 +
Alembic**. Управление зависимостями — Poetry (lock-файл). Тесты — на SQLite
(aiosqlite). Enum'ы хранятся как VARCHAR (`native_enum=False`) для переносимости.

## Rationale

FastAPI закрывает три обязательных драйвера сразу: async, Pydantic-валидацию и
автодокументацию (требование ТЗ «Swagger/OpenAPI» выполняется «бесплатно»).
Async-стек до самой БД (asyncpg) исключает блокировки при вызовах AI/SMTP.
SQLite в тестах даёт скорость и изоляцию без внешней инфраструктуры. Django был
бы избыточен под один публичный эндпоинт.

## Consequences

- Positive: единый async-стек без блокировок; документация генерируется сама;
  тесты не требуют Postgres; воспроизводимые сборки через lock.
- Negative: нужно аккуратно разводить сессии БД (решено в ADR-0004: отдельная
  сессия для фоновой задачи).
- Risks + Mitigation: расхождение SQLite (тесты) и Postgres (прод) → миграции
  прогоняются на реальном Postgres в CI (`alembic upgrade head`), типы enum'ов
  унифицированы как VARCHAR.

## Related
ADR-0004 (фоновые задачи и сессии БД). См. docs/architecture.md.
