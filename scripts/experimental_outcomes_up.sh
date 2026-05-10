#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/experimental_outcomes.pid"
LOG_FILE="$ROOT_DIR/.runtime/experimental_outcomes.log"

mkdir -p "$ROOT_DIR/.runtime"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Experimental outcomes scheduler ya está activo con PID $PID"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

source "$ROOT_DIR/.venv/bin/activate"
nohup "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/experimental_outcomes_scheduler.py" \
  --interval-seconds "${EXPERIMENTAL_OUTCOMES_INTERVAL_SECONDS:-3600}" \
  > "$LOG_FILE" 2>&1 < /dev/null &!

echo $! > "$PID_FILE"
sleep 1

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Experimental outcomes scheduler levantado con PID $PID"
else
  echo "El experimental outcomes scheduler no arrancó correctamente"
  exit 1
fi

