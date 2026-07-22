# TASK-001: Backend-сервис формы обратной связи с AI-обработкой
Status: done · Priority: H

## Goal
Рабочий REST-бэкенд формы обратной связи для лендинга разработчика, который
проходит полный цикл `запрос → валидация → бизнес-логика → AI → email → ответ`,
запускается одной командой и покрыт тестами.

## Context / Why
Тестовое задание (backend-ориентированное). Оценивается качество backend-кода,
проектирование API, обработка ошибок, AI-интеграция и организация проекта.
Пожелания заказчика: Python + FastAPI + Postgres, CI/CD, Docker, docs с
архитектурой.

## Scope
IN:
- `POST /api/contact`: валидация (имя/телефон/email/комментарий) → сохранение →
  фон: AI-анализ + 2 письма → `202`.
- AI-функция с graceful fallback (тональность+категория+приоритет+ответ).
- Rate limiting, логирование запросов в файл, глобальный error handler, CORS,
  Swagger/OpenAPI.
- Доп. эндпоинты: `/api/health`, `/api/metrics`.
- Слоистая архитектура (controllers→services→repositories), Docker, CI/CD,
  docs (architecture/ADR/PRR), README, Postman.

OUT (в этой задаче не делаем):
- Фронтенд формы (можно отдельным TASK — большой плюс, но не обязателен).
- Внешняя очередь задач (Celery/arq) — при росте нагрузки, отдельный TASK.
- Капча/honeypot, нагрузочное тестирование, централизованный алертинг.

## Affected files
- `app/**` — весь код приложения (core, api, services, repositories, models, db).
- `migrations/**` — Alembic (таблица `contacts`).
- `tests/**` — pytest (29 тестов).
- `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `render.yaml`.
- `.github/workflows/ci.yml` — CI/CD.
- `docs/**`, `README.md`, `postman_collection.json`, `.env.example`.

## Acceptance criteria (DoD)
- [x] `POST /api/contact` возвращает `202`, невалидный ввод → `422`, спам → `429`.
- [x] AI-анализ работает, при сбое реального AI — rule-based fallback (проверено тестом).
- [x] Отправляются 2 письма (владельцу + копия юзеру); в демо — `.eml` в logs.
- [x] Логи запросов пишутся в файл (`logs/app.jsonl`), есть request_id.
- [x] Тесты зелёные: `pytest` → 29 passed, coverage ~78%.
- [x] Линтер чистый: `ruff check app tests`.
- [x] Миграции применяются к чистой БД (`alembic check` → нет расхождений).
- [x] Swagger доступен на `/docs`; Postman-коллекция приложена.
- [x] Docker: `docker compose up --build` поднимает весь стек.
- [x] CI/CD настроен (GitHub Actions), деплой на Render описан.
- [x] docs обновлены: architecture (C4), api, ai-integration, ADR×5, PRR, ci-cd,
      code-review.
- [x] Smoke E2E: живой сервер отвечает по всем эндпоинтам.

## Notes / Risks
- AI по умолчанию `mock` (rule-based) — запуск без ключей; реальный Claude за
  флагом `AI_PROVIDER=anthropic` (из РФ нужен прокси). См. ADR-0003.
- CORS=* — демо-дефолт, для прода сузить (Risk Register в PRR).
