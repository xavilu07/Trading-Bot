#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/api.pid"

if [[ ! -f "$PID_FILE" ]]; then
  EXISTING_PID="$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$EXISTING_PID" ]]; then
    echo "No hay PID registrado"
    exit 0
  fi
  PID="$EXISTING_PID"
else
  PID="$(cat "$PID_FILE")"
fi

if ! kill -0 "$PID" 2>/dev/null; then
  EXISTING_PID="$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$EXISTING_PID" ]]; then
    PID="$EXISTING_PID"
  fi
fi

if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi
  echo "API detenida"
else
  echo "El proceso ya no estaba activo"
fi

rm -f "$PID_FILE"
