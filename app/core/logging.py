"""Структурное логирование на structlog.

- В файл `logs/app.jsonl` пишутся строки JSON (по одной на событие) — удобно
  парсить и грепать; выполняет требование ТЗ «логирование в файл».
- В консоль в dev выводится человекочитаемый цветной формат.
- `request_id` прокидывается через contextvars и попадает в каждую запись,
  что даёт сквозную трассировку одного HTTP-запроса через все слои.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog
from structlog.contextvars import merge_contextvars

from app.core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.jsonl"

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Общие процессоры для обоих приёмников (файл + консоль).
    shared_processors: list[structlog.typing.Processor] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Файловый handler — всегда JSON.
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    )

    # Консольный handler — JSON в проде, цветной human-readable в dev.
    console_handler = logging.StreamHandler(sys.stdout)
    console_renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=True)
    )
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=console_renderer,
            foreign_pre_chain=shared_processors,
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.setLevel(level)

    # Приглушаем слишком болтливые сторонние логгеры.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
