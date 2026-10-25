#!/bin/sh
# Startup sequence for local development (see spec/LOCAL_DEVELOPMENT.md):
#   1. make sure the SQLite directory exists,
#   2. apply migrations (failure stops the container with a non-zero code),
#   3. optionally seed idempotent demo data,
#   4. start the development server.
set -eu

DB_PATH="${DJANGO_DB_PATH:-/app/data/db.sqlite3}"
DB_DIR=$(dirname "$DB_PATH")
mkdir -p "$DB_DIR"

# Inside the image the venv provides `python`; outside it fall back to `uv run`.
if command -v python >/dev/null 2>&1; then
  PY="python"
else
  PY="uv run python"
fi

echo "[entrypoint] Applying database migrations to ${DB_PATH} ..."
$PY manage.py migrate --noinput

if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then
  echo "[entrypoint] Seeding demo data (idempotent) ..."
  $PY manage.py seed_demo_data
else
  echo "[entrypoint] SEED_DEMO_DATA is not 1 — skipping demo data."
fi

echo "[entrypoint] Starting development server on 0.0.0.0:8000"
exec $PY manage.py runserver 0.0.0.0:8000
