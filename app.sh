#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# app.sh — start FastURL
# Usage: ./app.sh          → start the server with the number of workers from config.yaml
#        ./app.sh --reload → with auto-reload for local development (single worker)
# -----------------------------------------------------------------------------
set -euo pipefail

# Read the configuration from config.yaml through the application settings
HOST=$(PYTHONPATH=src uv run python -c "from fasturl.core.config import settings; print(settings.app.host)" 2>/dev/null || echo "127.0.0.1")
PORT=$(PYTHONPATH=src uv run python -c "from fasturl.core.config import settings; print(settings.app.port)" 2>/dev/null || echo "8000")
WORKERS=$(PYTHONPATH=src uv run python -c "from fasturl.core.config import settings; print(settings.app.workers)" 2>/dev/null || echo "1")

if [[ "${1:-}" == "--reload" ]]; then
  PYTHONPATH=src uv run python -m fasturl.core.config 1 || true
  echo "Starting FastURL in development mode with --reload on ${HOST}:${PORT} (single worker)..."
  PYTHONPATH=src uv run uvicorn fasturl.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --reload
else
  PYTHONPATH=src uv run python -m fasturl.core.config "${WORKERS}" || true
  echo "Starting FastURL on ${HOST}:${PORT} with ${WORKERS} worker(s)..."
  PYTHONPATH=src uv run uvicorn fasturl.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}"
fi
