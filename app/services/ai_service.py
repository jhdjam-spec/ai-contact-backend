"""AI-сервис: оркестрация провайдеров, circuit breaker и graceful fallback.

Логика надёжности (требование ТЗ «сервис продолжает работать, если AI недоступен»):

1. Основной провайдер выбирается настройкой AI_PROVIDER.
2. Вызов защищён таймаутом (AI_TIMEOUT_SECONDS) и circuit breaker'ом:
   после N подряд сбоев «цепь размыкается» и запросы на время идут сразу в
   fallback, не тратя время на заведомо мёртвый сервис.
3. Fallback — MockAIProvider (rule-based), он не ходит в сеть и не падает.

Таким образом обращение пользователя обрабатывается ВСЕГДА, даже при полном
отказе внешнего AI.
"""

from __future__ import annotations

import asyncio
import time

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIResult
from app.services.ai.base import AIProvider
from app.services.ai.mock_provider import MockAIProvider

logger = get_logger("ai.service")


class CircuitBreaker:
    """Простой circuit breaker: OPEN на `cooldown` секунд после `threshold`
    подряд идущих сбоев. Пока цепь разомкнута, `allow()` возвращает False и
    сервис сразу использует fallback."""

    def __init__(self, threshold: int = 3, cooldown: float = 30.0) -> None:
        self._threshold = threshold
        self._cooldown = cooldown
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if (time.monotonic() - self._opened_at) >= self._cooldown:
            # Полуоткрытое состояние: даём одну попытку.
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning("circuit_breaker_open", failures=self._failures)

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None and not self.allow()


def _build_primary(settings: Settings) -> AIProvider:
    if settings.ai_provider == "anthropic":
        try:
            from app.services.ai.anthropic_provider import AnthropicAIProvider

            return AnthropicAIProvider()
        except Exception as exc:  # ключ не задан / пакет недоступен
            logger.warning("anthropic_init_failed_fallback_to_mock", error=str(exc))
            return MockAIProvider()
    return MockAIProvider()


class AIService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._primary = _build_primary(self._settings)
        self._fallback = MockAIProvider()
        self._breaker = CircuitBreaker()
        self._timeout = self._settings.ai_timeout_seconds

    @property
    def primary_name(self) -> str:
        return self._primary.name

    @property
    def degraded(self) -> bool:
        """True, если основной провайдер сейчас недоступен (цепь разомкнута)."""
        return self._breaker.is_open

    async def analyze(self, *, name: str, comment: str) -> AIResult:
        # Если основной провайдер — уже mock, незачем городить fallback.
        if isinstance(self._primary, MockAIProvider):
            return await self._primary.analyze(name=name, comment=comment)

        if not self._breaker.allow():
            logger.info("ai_circuit_open_use_fallback")
            return await self._fallback.analyze(name=name, comment=comment)

        try:
            result = await asyncio.wait_for(
                self._primary.analyze(name=name, comment=comment),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            return await self._on_failure("timeout", exc, name=name, comment=comment)
        except Exception as exc:  # noqa: BLE001 — намеренно ловим всё ради fallback
            return await self._on_failure("error", exc, name=name, comment=comment)
        else:
            self._breaker.record_success()
            return result

    async def _on_failure(
        self, kind: str, exc: BaseException, *, name: str, comment: str
    ) -> AIResult:
        self._breaker.record_failure()
        logger.warning(
            "ai_primary_failed_fallback",
            provider=self._primary.name,
            kind=kind,
            error=str(exc),
        )
        # Graceful fallback: rule-based анализ вместо отказа.
        return await self._fallback.analyze(name=name, comment=comment)


# Синглтон сервиса (провайдер создаётся один раз на процесс).
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
