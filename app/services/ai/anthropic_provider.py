"""Реальный AI-провайдер на Anthropic Claude (tool-use / structured output).

Включается через AI_PROVIDER=anthropic + ANTHROPIC_API_KEY. Использует
forced tool-use: модель обязана вызвать инструмент submit_analysis, что
гарантирует валидный JSON нужной схемы (без парсинга «сырого» текста).

Из РФ требуется прокси-шлюз — задаётся через ANTHROPIC_BASE_URL (см. ADR-0003
и правило безопасности п.6 из глобальных инструкций).
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.contact import AIResult
from app.services.ai.base import AIProvider
from app.services.ai.prompts import (
    ANALYZE_TOOL,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
)

logger = get_logger("ai.anthropic")


class AnthropicAIProvider(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY не задан — провайдер anthropic недоступен")

        # Импорт локальный: пакет нужен только при активном провайдере.
        from anthropic import AsyncAnthropic

        self._model = settings.anthropic_model
        self._timeout = settings.ai_timeout_seconds
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            base_url=settings.anthropic_base_url or None,
            timeout=settings.ai_timeout_seconds,
        )

    async def analyze(self, *, name: str, comment: str) -> AIResult:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[ANALYZE_TOOL],
            tool_choice={"type": "tool", "name": ANALYZE_TOOL["name"]},
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(name=name, comment=comment),
                }
            ],
        )

        payload = self._extract_tool_input(message)
        return AIResult(
            sentiment=payload["sentiment"],
            category=payload["category"],
            priority=payload["priority"],
            suggested_reply=payload["suggested_reply"].strip(),
            provider=self.name,
        )

    @staticmethod
    def _extract_tool_input(message) -> dict:
        """Достаём аргументы вызванного инструмента из ответа Claude."""
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        raise ValueError("Claude не вернул tool_use блок с анализом")
