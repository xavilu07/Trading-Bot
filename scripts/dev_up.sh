#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/api.pid"
LOG_FILE="$ROOT_DIR/.runtime/api.log"

mkdir -p "$ROOT_DIR/.runtime"

EXISTING_PID="$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "API ya está levantada con PID $PID"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

if [[ -n "$EXISTING_PID" ]]; then
  echo "$EXISTING_PID" > "$PID_FILE"
  echo "API ya estaba activa en el puerto 8000 con PID $EXISTING_PID"
  exit 0
fi

source "$ROOT_DIR/.venv/bin/activate"
nohup "$ROOT_DIR/.venv/bin/uvicorn" trading_signals.interfaces.api.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  > "$LOG_FILE" 2>&1 < /dev/null &!

echo $! > "$PID_FILE"
sleep 1

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "API levantada en http://127.0.0.1:8000 con PID $PID"
else
  echo "La API no arrancó correctamente"
  exit 1
fi
