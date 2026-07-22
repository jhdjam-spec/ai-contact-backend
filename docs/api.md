# API

Базовый URL (локально): `http://localhost:8000`
Интерактивная документация: **`/docs`** (Swagger UI), **`/redoc`** (ReDoc),
машинная схема — `/openapi.json`.

Все ответы — JSON. Ошибки имеют единый конверт:

```json
{
  "error": { "code": "validation_error", "message": "...", "details": [ ... ] },
  "request_id": "3f9a1c..."
}
```

`request_id` дублируется в заголовке ответа `X-Request-ID` и в логах — по нему
ошибку из ответа можно найти в `logs/app.jsonl`.

---

## POST /api/contact

Приём обращения с формы обратной связи. Обработка AI и рассылка писем —
асинхронные, поэтому ответ приходит сразу со статусом `202 Accepted`.

### Запрос

| Поле | Тип | Правила |
|------|-----|---------|
| `name` | string | 2–120 символов, без цифр и спецсимволов `<>@/\{}[]` |
| `email` | string | валидный email (RFC), проверяется `email-validator` |
| `phone` | string | валидный номер; нормализуется в E.164 (`+79001234567`) |
| `comment` | string | 5–4000 символов |

Лишние поля запрещены (`extra="forbid"`) — защита от инъекций мусора.

```json
{
  "name": "Иван Петров",
  "email": "ivan@example.com",
  "phone": "+7 900 123-45-67",
  "comment": "Здравствуйте! Хотим предложить проект по разработке backend."
}
```

### Ответы

| Код | Когда | Тело |
|-----|-------|------|
| `202 Accepted` | принято | `{"id": 1, "status": "received", "message": "..."}` |
| `422 Unprocessable Content` | ошибка валидации | конверт ошибки с `details[]` |
| `429 Too Many Requests` | превышен rate limit | конверт ошибки |

Пример `202`:

```json
{ "id": 1, "status": "received", "message": "Обращение принято и обрабатывается" }
```

Пример `422`:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Некорректные входные данные",
    "details": [{ "field": "phone", "reason": "Некорректный номер телефона" }]
  },
  "request_id": "a1b2c3d4"
}
```

### curl

```bash
curl -sS -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Иван Петров",
    "email": "ivan@example.com",
    "phone": "+7 900 123-45-67",
    "comment": "Здравствуйте! Хотим предложить проект по разработке backend."
  }'
```

---

## GET /api/health

Проверка состояния сервиса и зависимостей. Возвращает `200`, если БД доступна,
иначе `503`.

```bash
curl -sS http://localhost:8000/api/health
```

```json
{
  "status": "healthy",
  "app": "AI Contact Backend",
  "version": "1.0.0",
  "env": "development",
  "checks": {
    "database": "ok",
    "ai_provider": "mock",
    "ai_degraded": false,
    "email_backend": "console"
  }
}
```

Поле `ai_degraded: true` означает, что основной AI-провайдер сейчас недоступен и
сервис работает на rule-based fallback.

---

## GET /api/metrics

Агрегированная статистика обращений из БД.

```bash
curl -sS http://localhost:8000/api/metrics
```

```json
{
  "total": 12,
  "by_status": { "processed": 11, "received": 1 },
  "by_sentiment": { "positive": 5, "neutral": 6, "negative": 1 },
  "by_category": { "job_offer": 3, "project": 6, "question": 2, "spam": 1 },
  "by_priority": { "high": 9, "medium": 2, "low": 1 }
}
```

---

## Rate limiting

Лимит по IP задаётся настройкой `RATE_LIMIT_CONTACT` (по умолчанию `5/minute`).
За обратным прокси (Render) IP берётся из заголовка `X-Forwarded-For`.
При превышении — `429` с конвертом ошибки.
