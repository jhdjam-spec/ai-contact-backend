"""Тесты AI-сервиса: rule-based провайдер, circuit breaker и graceful fallback."""

from __future__ import annotations

import asyncio

from app.models.contact import Category, Priority, Sentiment
from app.schemas.contact import AIResult
from app.services.ai.base import AIProvider
from app.services.ai.mock_provider import MockAIProvider
from app.services.ai_service import AIService, CircuitBreaker

# --- MockAIProvider (rule-based) ---


async def test_mock_detects_job_offer():
    provider = MockAIProvider()
    result = await provider.analyze(
        name="HR", comment="У нас открыта вакансия, готовы обсудить оффер и зарплату."
    )
    assert result.category == Category.JOB_OFFER
    assert result.priority == Priority.HIGH
    assert result.provider == "mock"
    assert result.suggested_reply  # черновик не пустой


async def test_mock_detects_negative_sentiment():
    provider = MockAIProvider()
    result = await provider.analyze(
        name="Пользователь", comment="Всё ужасно, ничего не работает, сплошные ошибки."
    )
    assert result.sentiment == Sentiment.NEGATIVE


async def test_mock_detects_spam_low_priority():
    provider = MockAIProvider()
    result = await provider.analyze(
        name="X", comment="Бесплатное продвижение SEO и заработок на крипте, click here"
    )
    assert result.category == Category.SPAM
    assert result.priority == Priority.LOW


# --- Circuit breaker ---


def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(threshold=3, cooldown=100)
    assert cb.allow()
    for _ in range(3):
        cb.record_failure()
    assert not cb.allow()  # цепь разомкнута
    assert cb.is_open


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(threshold=2, cooldown=100)
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert cb.allow()  # счётчик сбросился, одного сбоя мало


# --- Graceful fallback ---


class _BrokenProvider(AIProvider):
    name = "broken"

    async def analyze(self, *, name: str, comment: str) -> AIResult:
        raise RuntimeError("AI провайдер недоступен")


class _SlowProvider(AIProvider):
    name = "slow"

    async def analyze(self, *, name: str, comment: str) -> AIResult:
        await asyncio.sleep(5)  # дольше таймаута
        raise AssertionError("не должно быть достигнуто")


async def test_fallback_on_provider_error():
    service = AIService()
    service._primary = _BrokenProvider()  # подменяем основной на «сломанный»
    result = await service.analyze(name="Иван", comment="Хочу заказать проект")
    # Сервис не упал, вернул результат от fallback (mock).
    assert result.provider == "mock"
    assert result.category == Category.PROJECT


async def test_fallback_on_timeout():
    service = AIService()
    service._primary = _SlowProvider()
    service._timeout = 0.1
    result = await service.analyze(name="Иван", comment="Вопрос по вашему стеку?")
    assert result.provider == "mock"


async def test_degraded_flag_after_failures():
    service = AIService()
    service._primary = _BrokenProvider()
    for _ in range(3):
        await service.analyze(name="Иван", comment="тест")
    # После серии сбоев сервис помечен деградированным.
    assert service.degraded
