# AI Contact Backend

Backend-сервис формы обратной связи для лендинга разработчика с REST API и
AI-обработкой обращений. Полный цикл: **валидация → сохранение → AI-анализ →
email → ответ**.

![python](https://img.shields.io/badge/python-3.12-blue)
![fastapi](https://img.shields.io/badge/FastAPI-async-009688)
![tests](https://img.shields.io/badge/tests-29%20passed-success)
![coverage](https://img.shields.io/badge/coverage-~78%25-green)

> Тестовое задание (backend-ориентированное). Сделан упор на архитектуру,
> обработку ошибок, безопасность и надёжную AI-интеграцию с graceful fallback.

## TL;DR — запуск за 30 секунд

```bash
git clone <repo> && cd ai-contact-backend
cp .env.example .env
docker compose up --build
```

Открыть **http://localhost:8000/docs** (Swagger). Сервис стартует **без единого
секрета**: AI работает на rule-based провайдере, письма пишутся в `logs/emails/`.

---

## Содержание

1. [Как запустить](#1-как-запустить)
2. [Стек технологий](#2-стек-технологий)
3. [Архитектура](#3-архитектура)
4. [Реализация API](#4-реализация-api)
5. [AI-интеграция](#5-ai-интеграция)
6. [Что сделано с помощью AI](#6-что-сделано-с-помощью-ai)
7. [Хранение данных](#7-хранение-данных)
8. [Тесты и качество](#8-тесты-и-качество)
9. [Деплой](#9-деплой)

---

## 1. Как запустить

### Вариант A — Docker (рекомендуется)

```bash
cp .env.example .env
docker compose up --build
```

Поднимает три контейнера: приложение, PostgreSQL 16, Redis. Миграции
применяются автоматически при старте. API — на `http://localhost:8000`.

### Вариант B — локально (Poetry)

Нужен Python 3.12+ и запущенный PostgreSQL (или SQLite — см. ниже).

```bash
poetry install
cp .env.example .env

# Для локали без Docker удобно взять SQLite (правка .env):
#   DATABASE_URL=sqlite+aiosqlite:///./app.db

poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

### Переменные окружения

Все настройки — в `.env` (пример: `.env.example`). Дефолты рассчитаны на запуск
без секретов. Ключевые:

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `DATABASE_URL` | `postgresql+asyncpg://app:app@postgres:5432/contacts` | подключение к БД (авто-нормализуется из `postgres://`) |
| `AI_PROVIDER` | `mock` | `mock` (rule-based) или `anthropic` (Claude) |
| `EMAIL_BACKEND` | `console` | `console` (в файл) или `smtp` |
| `RATE_LIMIT_CONTACT` | `5/minute` | лимит на `/api/contact` по IP |
| `CORS_ORIGINS` | `*` | разрешённые origins (в проде сузить) |
| `ANTHROPIC_API_KEY` | — | ключ для реального Claude |
| `SMTP_*` | — | параметры реального SMTP |

---

## 2. Стек технологий

**Backend:** Python 3.12, FastAPI (async), Uvicorn, Pydantic v2.
**БД:** PostgreSQL 16 + SQLAlchemy 2.0 (async, asyncpg) + Alembic. Тесты — SQLite.
**AI:** Anthropic Claude (tool-use) с fallback на собственный rule-based анализатор.
**Инфраструктура:** structlog (JSON-логи), slowapi (rate limit), fastapi-mail/
aiosmtplib (email), phonenumbers + email-validator (валидация).
**DevOps:** Docker (multi-stage), docker-compose, GitHub Actions, Render.
**Качество:** pytest, pytest-asyncio, coverage, ruff, mypy.

Обоснование выбора — в [docs/adr/0002-fastapi-async-stack.md](docs/adr/0002-fastapi-async-stack.md).

---

## 3. Архитектура

**Слоистая структура** (зависимость строго сверху вниз):

```
API / Routers  ->  Services  ->  Repositories  ->  Models / DB
   (app/api)     (app/services) (app/repositories) (app/models, app/db)
                      |
         Strategy: AI (mock/anthropic), Email (console/smtp)

Cross-cutting: app/core (config, logging, errors, rate_limit, middleware)
```

Структура проекта:

```
app/
├── main.py              # сборка FastAPI (lifespan, middleware, CORS, роутеры)
├── core/                # config, logging, errors, rate_limit, middleware
├── api/v1/              # роутеры: contact, health, metrics + deps (DI)
├── schemas/             # Pydantic-контракты + валидация
├── services/            # бизнес-логика
│   ├── contact_service.py   # оркестрация цикла + фоновая обработка
│   ├── ai_service.py        # circuit breaker + fallback
│   ├── ai/                  # провайдеры: base, mock, anthropic, prompts
│   └── email_service.py     # console / smtp отправители
├── repositories/        # доступ к данным (SQLAlchemy)
├── models/              # ORM-модель Contact
└── db/                  # engine, session, base
docs/                    # architecture (C4), api, ai-integration, ADR, PRR, ci-cd, code-review
migrations/              # Alembic
tests/                   # pytest (29 тестов)
```

**Паттерны:** слоистая архитектура, Repository, Strategy (AI/email провайдеры),
Dependency Injection (FastAPI `Depends`), Circuit Breaker (надёжность AI).

Подробно с C4-диаграммами — [docs/architecture.md](docs/architecture.md).
Решения — [docs/adr/](docs/adr/). Готовность к проду — [docs/prr.md](docs/prr.md).

---

## 4. Реализация API

| Метод | Путь | Назначение |
|-------|------|------------|
| `POST` | `/api/contact` | приём обращения (валидация -> сохранение -> фон: AI + email) |
| `GET` | `/api/health` | состояние сервиса + проверка БД/AI |
| `GET` | `/api/metrics` | статистика обращений |
| `GET` | `/docs`, `/redoc` | Swagger UI / ReDoc |

**Валидация:** имя (2–120, без цифр/спецсимволов), email (RFC), телефон
(нормализация в E.164), комментарий (5–4000). Лишние поля запрещены.

**Обработка ошибок:** глобальный handler, единый JSON-конверт с `request_id`,
корректные статусы (`202` / `422` / `429` / `500`).

Полное описание с примерами запросов/ответов — [docs/api.md](docs/api.md).
Готовая **Postman-коллекция** — [postman_collection.json](postman_collection.json).

Быстрый пример:

```bash
curl -sS -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{"name":"Иван Петров","email":"ivan@example.com","phone":"+7 900 123-45-67","comment":"Хотим предложить проект по разработке backend."}'
# -> 202 {"id":1,"status":"received","message":"Обращение принято и обрабатывается"}
```

---

## 5. AI-интеграция

Один вызов AI анализирует обращение сразу по 4 осям: **тональность**,
**категория** (job_offer/project/question/spam/other), **приоритет** и
**черновик ответа**.

**Graceful fallback** (требование ТЗ): `AIService` защищён таймаутом и
**circuit breaker**'ом; при сбое реального AI автоматически падает на встроенный
**rule-based** анализатор, который не ходит в сеть. Обращение обрабатывается
всегда, даже при полном отказе внешнего AI.

Провайдер выбирается флагом `AI_PROVIDER` (mock по умолчанию / anthropic).
Промпты, схема fallback и обоснование — [docs/ai-integration.md](docs/ai-integration.md)
и [ADR-0003](docs/adr/0003-ai-provider-abstraction.md).

---

## 6. Что сделано с помощью AI

Проект написан в паре с AI-ассистентом. Прозрачный самоотчёт (что генерировалось,
какие промпты, что правилось вручную) — в
[docs/ai-integration.md](docs/ai-integration.md#что-сделано-с-помощью-ai-самоотчёт).
Кратко: AI сгенерировал каркас слоёв, boilerplate, словари mock-провайдера, тесты
и инфраструктуру; вручную дорабатывались доменные enum'ы, логика circuit breaker
(half-open), нормализация `postgres://`-URL и подмена фонового sessionmaker в тестах.

---

## 7. Хранение данных

**PostgreSQL** — основное хранилище (таблица `contacts`): данные формы,
результат AI-анализа, статус обработки, `client_ip`, `request_id`, `created_at`.
Схема версионируется Alembic-миграциями.

- **Логи запросов** — `logs/app.jsonl` (structlog, JSON построчно, с request_id).
- **Rate limiting** — in-memory по умолчанию, Redis при заданном `REDIS_URL`.
- **Статистика** — агрегируется из БД на лету (`GET /api/metrics`).
- **Письма (демо)** — `logs/emails/*.eml` (console-бэкенд).

Почему БД, а не файлы: ТЗ даёт плюс за навыки работы с БД; при этом файловое
хранение логов/писем тоже показано.

---

## 8. Тесты и качество

```bash
poetry run pytest --cov=app          # 29 тестов, coverage ~78%
poetry run ruff check app tests      # линтер
```

Покрыто: валидация (включая E.164 и запрет лишних полей), полный цикл обработки,
rule-based анализ, **circuit breaker и fallback**, rate limit, health, metrics,
нормализация DATABASE_URL, единый конверт ошибок.

Гайд по код-ревью — [docs/code-review.md](docs/code-review.md).

---

## 9. Деплой

**Render** (Blueprint `render.yaml`): web-сервис из Docker + managed PostgreSQL.
CI/CD — GitHub Actions (`lint -> test -> build -> deploy`). Инструкция и грабли
(в т.ч. авто-нормализация `postgres://`-URL) — [docs/ci-cd.md](docs/ci-cd.md).

Если деплой недоступен — проект полностью работает локально одной командой
`docker compose up --build` (см. раздел 1).

---

## Лицензия

MIT.
