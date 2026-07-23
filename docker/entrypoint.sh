#!/usr/bin/env bash
# Entrypoint контейнера: применяем миграции, затем запускаем переданную команду.
# Миграции идемпотентны (alembic upgrade head), поэтому безопасно на каждом старте.
set -euo pipefail

echo "[entrypoint] Applying database migrations..."
# Не роняем контейнер, если БД ещё не готова на первой попытке — короткий ретрай.
for attempt in 1 2 3 4 5; do
  if python -m alembic upgrade head; then
    echo "[entrypoint] Migrations applied."
    break
  fi
  echo "[entrypoint] DB not ready (attempt ${attempt}/5), retrying in 3s..."
  sleep 3
done

echo "[entrypoint] Starting: $*"
exec "$@"
