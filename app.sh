#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# app.sh — avvia FastURL in modalità sviluppo
# Uso: ./app.sh         → senza auto-reload (nessun warning semafori)
#      ./app.sh --reload → con auto-reload (ricarica codice al salvataggio)
# -----------------------------------------------------------------------------
set -euo pipefail

# Crea la directory del database se non esiste
mkdir -p instance

RELOAD_FLAG=""
if [[ "${1:-}" == "--reload" ]]; then
  RELOAD_FLAG="--reload"
fi

PYTHONPATH=src uv run uvicorn fasturl.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  $RELOAD_FLAG
