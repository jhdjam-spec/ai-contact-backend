"""Контракт AI-провайдера (паттерн Strategy).

Любой провайдер (mock, anthropic, в будущем gigachat/openai) реализует один
метод `analyze`. Это позволяет менять реализацию через настройку AI_PROVIDER
без изменения бизнес-логики и делает возможным graceful fallback.
"""

from __future__ import annotations

import abc

from app.schemas.contact import AIResult


class AIProvider(abc.ABC):
    """Абстрактный AI-провайдер анализа обращений."""

    name: str = "base"

    @abc.abstractmethod
    async def analyze(self, *, name: str, comment: str) -> AIResult:
        """Проанализировать обращение.

        Возвращает AIResult (тональность, категория, приоритет, черновик
        ответа). Должен либо вернуть валидный результат, либо бросить
        исключение — обработка сбоя и fallback лежат на оркестраторе.
        """
        raise NotImplementedError
