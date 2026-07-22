# Архитектура

Документ описывает архитектуру сервиса обратной связи: компоненты, слои,
потоки данных. Диаграммы — в нотации [C4](https://c4model.com/) на Mermaid
(рендерятся прямо на GitHub).

## 1. Контекст (C4 Level 1)

```mermaid
flowchart LR
    visitor["Посетитель лендинга"] -->|"заполняет форму"| api["AI Contact Backend<br/>(FastAPI)"]
    owner["Владелец сайта"] -->|"читает уведомления"| mailbox["Почтовый ящик"]

    api -->|"письмо владельцу + копия юзеру"| smtp["SMTP / Console"]
    api -->|"анализ обращения"| ai["AI-провайдер<br/>(Claude / rule-based)"]
    api -->|"хранение"| db[("PostgreSQL")]
    smtp --> mailbox
```

Сервис принимает обращения с формы обратной связи, анализирует их AI-инструментом
(тональность, категория, приоритет, черновик ответа), сохраняет в БД и рассылает
два письма: уведомление владельцу и подтверждение отправителю.

## 2. Контейнеры (C4 Level 2)

```mermaid
flowchart TB
    subgraph client["Клиент"]
        form["HTML-форма / Postman / curl"]
    end

    subgraph app["FastAPI-приложение"]
        mw["Middleware<br/>request_id + логи + rate limit + CORS"]
        routers["API Routers<br/>/api/contact, /health, /metrics"]
        services["Services<br/>Contact / AI / Email"]
        repo["Repository<br/>SQLAlchemy async"]
    end

    db[("PostgreSQL 16")]
    redis[("Redis<br/>rate-limit store")]
    ai["AI-провайдер"]
    smtp["SMTP / Console"]
    logs["logs/app.jsonl"]

    form -->|"HTTP JSON"| mw --> routers --> services
    services --> repo --> db
    mw -. "лимиты" .-> redis
    services -->|"фон"| ai
    services -->|"фон"| smtp
    app --> logs
```

## 3. Компоненты и слои (C4 Level 3)

Приложение построено по **слоистой архитектуре** — зависимость строго сверху вниз,
каждый слой знает только о нижнем:

```mermaid
flowchart TB
    R["API / Routers<br/>app/api"] --> S["Services<br/>app/services"]
    S --> RP["Repositories<br/>app/repositories"]
    RP --> M["Models / DB<br/>app/models, app/db"]
    S -.-> AIP["AI Providers<br/>Strategy: mock | anthropic"]
    S -.-> EM["Email Senders<br/>Strategy: console | smtp"]

    subgraph cross["Cross-cutting (app/core)"]
        C1["config"]
        C2["logging"]
        C3["errors"]
        C4["rate_limit"]
        C5["middleware"]
    end
```

| Слой | Каталог | Ответственность |
|------|---------|-----------------|
| **API / Routers** | `app/api` | HTTP-контракт, коды ответов, DI. Без бизнес-логики. |
| **Services** | `app/services` | Бизнес-логика, оркестрация, AI и email как стратегии. |
| **Repositories** | `app/repositories` | Доступ к данным, инкапсуляция SQLAlchemy. |
| **Models / DB** | `app/models`, `app/db` | ORM-модели, сессии, миграции. |
| **Core** | `app/core` | Сквозная функциональность: конфиг, логи, ошибки, лимиты. |

## 4. Поток обработки обращения (полный цикл)

```mermaid
sequenceDiagram
    participant U as Клиент
    participant M as Middleware
    participant R as Router /api/contact
    participant CS as ContactService
    participant Repo as Repository
    participant DB as PostgreSQL
    participant BG as BackgroundTask
    participant AI as AIService
    participant EM as EmailService

    U->>M: POST /api/contact
    M->>M: request_id, лог, rate limit, CORS
    M->>R: валидированный запрос (Pydantic)
    R->>CS: submit(payload)
    CS->>Repo: create(contact)
    Repo->>DB: INSERT (status=received)
    CS-->>U: 202 Accepted {id, status}
    Note over R,BG: HTTP-ответ отдан, дальше — фон
    R->>BG: process_in_background(id, payload)
    BG->>AI: analyze(name, comment)
    AI-->>BG: {sentiment, category, priority, reply}
    Note right of AI: при сбое — circuit breaker<br/>+ rule-based fallback
    BG->>Repo: apply_ai_result(id, result)
    Repo->>DB: UPDATE (AI-поля)
    BG->>EM: send_notifications (2 письма)
    BG->>Repo: set_status(processed)
```

**Ключевое решение:** тяжёлые операции (AI, SMTP) вынесены в фоновую задачу,
поэтому клиент получает ответ `202 Accepted` за десятки миллисекунд, не дожидаясь
внешних сервисов. Подробнее — [ADR-0004](adr/0004-background-tasks.md).

## 5. Надёжность

- **Graceful fallback AI** — [ADR-0003](adr/0003-ai-provider-abstraction.md):
  circuit breaker + rule-based провайдер. Обращение обрабатывается всегда.
- **Независимая отправка писем** — сбой одного письма не отменяет второе.
- **Идемпотентные миграции** — `alembic upgrade head` на каждом старте контейнера.
- **Health с проверкой зависимостей** — `/api/health` пингует БД.

## 6. Модель данных

Единственная таблица `contacts` (см. `app/models/contact.py`):

| Группа | Поля |
|--------|------|
| Данные формы | `name`, `email`, `phone` (E.164), `comment` |
| AI-результат | `sentiment`, `category`, `priority`, `suggested_reply`, `ai_provider` |
| Служебное | `status`, `client_ip`, `request_id`, `created_at` |

Enum'ы хранятся как VARCHAR (`native_enum=False`) — переносимо между Postgres и
SQLite и не требует `ALTER TYPE` при добавлении категорий.
