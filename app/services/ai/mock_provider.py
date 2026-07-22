"""Rule-based AI-провайдер (он же offline-fallback).

Это НЕ пустая заглушка: реализован детерминированный анализ на словарях и
эвристиках — лексиконная тональность, классификация по ключевым словам,
шаблонный ответ под категорию. Работает без сети, ключей и внешних зависимостей.

Двойная роль (см. ADR-0003):
  1) провайдер по умолчанию (AI_PROVIDER=mock) — сервис запускается «из коробки»;
  2) fallback-слой, на который оркестратор падает при сбое реального AI.
"""

from __future__ import annotations

from app.models.contact import Category, Priority, Sentiment
from app.schemas.contact import AIResult
from app.services.ai.base import AIProvider

_POSITIVE_WORDS = {
    "спасибо", "благодарю", "отлично", "супер", "здорово", "рад", "рады",
    "нравится", "класс", "круто", "прекрасно", "замечательно", "восхищ",
}
_NEGATIVE_WORDS = {
    "плохо", "ужас", "разочарован", "недоволен", "ошибка", "не работает",
    "проблема", "жалоба", "верните", "отвратительно", "медленно", "баг",
}

_CATEGORY_KEYWORDS: dict[Category, set[str]] = {
    Category.JOB_OFFER: {
        "вакансия", "оффер", "offer", "позиция", "работу", "трудоустрой",
        "зарплата", "команду", "hr", "рекрут", "ставка", "релокейт",
    },
    Category.PROJECT: {
        "проект", "заказ", "разработать", "сделать сайт", "подряд",
        "сотрудничество", "бюджет", "техзадание", "тз", "интеграцию", "mvp",
    },
    Category.QUESTION: {
        "вопрос", "как вы", "используете ли", "опыт", "стек", "подскажите",
        "можно ли", "поддерживаете", "умеете", "?",
    },
    Category.SPAM: {
        "продвижение", "seo", "казино", "кредит", "выиграл", "бесплатно",
        "заработок", "инвестиции", "крипт", "розыгрыш", "click here", "http://",
    },
}

_REPLY_TEMPLATES: dict[Category, str] = {
    Category.JOB_OFFER: (
        "Здравствуйте, {name}! Спасибо за интерес к сотрудничеству — "
        "предложение о работе выглядит интересно. Давайте обсудим детали: "
        "ответьте, пожалуйста, на удобный вам способ связи, и я вернусь с уточнениями."
    ),
    Category.PROJECT: (
        "Здравствуйте, {name}! Благодарю за обращение по проекту. "
        "Готов обсудить задачу подробнее — опишите, пожалуйста, сроки и ключевые "
        "требования, и я подготовлю оценку."
    ),
    Category.QUESTION: (
        "Здравствуйте, {name}! Спасибо за вопрос. С удовольствием отвечу — "
        "уточните, пожалуйста, детали, и я вернусь с развёрнутым ответом в ближайшее время."
    ),
    Category.SPAM: (
        "Здравствуйте! Спасибо за сообщение, но, похоже, предложение не относится "
        "к моей сфере. Хорошего дня."
    ),
    Category.OTHER: (
        "Здравствуйте, {name}! Спасибо за обращение — я получил ваше сообщение "
        "и свяжусь с вами в ближайшее время."
    ),
}

_PRIORITY_BY_CATEGORY: dict[Category, Priority] = {
    Category.JOB_OFFER: Priority.HIGH,
    Category.PROJECT: Priority.HIGH,
    Category.QUESTION: Priority.MEDIUM,
    Category.OTHER: Priority.MEDIUM,
    Category.SPAM: Priority.LOW,
}


class MockAIProvider(AIProvider):
    name = "mock"

    async def analyze(self, *, name: str, comment: str) -> AIResult:
        text = comment.lower()

        sentiment = self._detect_sentiment(text)
        category = self._detect_category(text)
        priority = _PRIORITY_BY_CATEGORY.get(category, Priority.MEDIUM)
        reply = _REPLY_TEMPLATES[category].format(name=name)

        return AIResult(
            sentiment=sentiment,
            category=category,
            priority=priority,
            suggested_reply=reply,
            provider=self.name,
        )

    @staticmethod
    def _detect_sentiment(text: str) -> Sentiment:
        pos = sum(1 for w in _POSITIVE_WORDS if w in text)
        neg = sum(1 for w in _NEGATIVE_WORDS if w in text)
        if pos > neg:
            return Sentiment.POSITIVE
        if neg > pos:
            return Sentiment.NEGATIVE
        return Sentiment.NEUTRAL

    @staticmethod
    def _detect_category(text: str) -> Category:
        # Спам проверяем первым — у него высший приоритет распознавания.
        best: Category = Category.OTHER
        best_score = 0
        for category, keywords in _CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best = category
        return best
