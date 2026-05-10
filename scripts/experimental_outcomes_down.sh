#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/experimental_outcomes.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Experimental outcomes scheduler parado"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID"
  fi
  echo "Experimental outcomes scheduler detenido"
else
  echo "El proceso ya no estaba activo"
fi

rm -f "$PID_FILE"

