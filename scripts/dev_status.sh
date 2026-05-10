#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/api.pid"

if [[ ! -f "$PID_FILE" ]]; then
  EXISTING_PID="$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$EXISTING_PID" ]]; then
    echo "API activa con PID $EXISTING_PID en http://127.0.0.1:8000"
    exit 0
  fi
  echo "API parada"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "API activa con PID $PID en http://127.0.0.1:8000"
else
  EXISTING_PID="$(lsof -ti tcp:8000 -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$EXISTING_PID" ]]; then
    echo "$EXISTING_PID" > "$PID_FILE"
    echo "API activa con PID $EXISTING_PID en http://127.0.0.1:8000"
    exit 0
  fi
  rm -f "$PID_FILE"
  echo "API parada"
  exit 0
fi
