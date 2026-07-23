# syntax=docker/dockerfile:1
# ============================================================================
#  Multi-stage build. Stage 1 экспортирует зависимости из Poetry в requirements
#  и ставит их в изолированный слой; Stage 2 — тонкий runtime без Poetry.
# ============================================================================

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.4

RUN pip install "poetry==${POETRY_VERSION}" poetry-plugin-export

WORKDIR /build
COPY pyproject.toml poetry.lock* ./

# Экспортируем только прод-зависимости в requirements.txt и ставим в /install.
# packaging дописываем прямо в requirements и ставим через --target ровно в тот
# каталог, что прописан в runtime PYTHONPATH, — иначе pip считает пакет «уже
# удовлетворённым» в builder-образе и не кладёт его в /install (slowapi→limits→
# packaging, без него падает импорт app с ModuleNotFoundError).
RUN poetry export --without dev --without-hashes -f requirements.txt -o requirements.txt \
    && printf '\npackaging>=21\n' >> requirements.txt \
    && pip install --no-cache-dir --target=/install/lib/python3.12/site-packages -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/lib/python3.12/site-packages/bin:/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

# Непривилегированный пользователь.
RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=builder /install /install
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p logs/emails && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
