# Architecture Decision Records (ADR)

Значимые архитектурные решения фиксируются здесь в формате
[MADR](https://adr.github.io/madr/). Каждое решение — отдельный неизменяемый
файл; при пересмотре создаётся новый ADR со ссылкой на предыдущий.

| № | Решение | Статус |
|---|---------|--------|
| [0001](0001-record-architecture-decisions.md) | Вести ADR | Accepted |
| [0002](0002-fastapi-async-stack.md) | Стек: FastAPI + async SQLAlchemy + Postgres | Accepted |
| [0003](0003-ai-provider-abstraction.md) | Абстракция AI-провайдера + fallback | Accepted |
| [0004](0004-background-tasks.md) | AI и email — в BackgroundTasks | Accepted |
| [0005](0005-email-abstraction.md) | Абстракция email-отправителя | Accepted |
