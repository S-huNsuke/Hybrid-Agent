#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] running alembic migrations..."
  uv run alembic upgrade head
fi

echo "[entrypoint] starting api server..."
exec uv run uvicorn hybrid_agent.api.main:app --host 0.0.0.0 --port 8000
