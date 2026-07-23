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
# packaging ставим отдельно как страховку: poetry export иногда теряет эту
# транзитивную зависимость (slowapi→limits→packaging), без неё падает импорт app.
RUN poetry export --without dev --without-hashes -f requirements.txt -o requirements.txt \
    && pip install --prefix=/install -r requirements.txt \
    && pip install --prefix=/install packaging

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/bin:$PATH" \
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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
