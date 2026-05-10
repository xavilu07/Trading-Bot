#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/scheduler.pid"
LOG_FILE="$ROOT_DIR/.runtime/scheduler.log"

mkdir -p "$ROOT_DIR/.runtime"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    echo "Scheduler ya está levantado con PID $PID"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_IDS:-}" ]]; then
  echo "Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_IDS en el entorno"
  exit 1
fi

source "$ROOT_DIR/.venv/bin/activate"
nohup env \
  TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
  TELEGRAM_CHAT_IDS="${TELEGRAM_CHAT_IDS}" \
  SCAN_INTERVAL_SECONDS="${SCAN_INTERVAL_SECONDS:-900}" \
  PUBLISH_SIGNAL_DECISIONS="${PUBLISH_SIGNAL_DECISIONS:-long}" \
  "$ROOT_DIR/.venv/bin/python" -m trading_signals.app.cli scheduler \
  > "$LOG_FILE" 2>&1 < /dev/null &!

echo $! > "$PID_FILE"
sleep 1

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Scheduler levantado con PID $PID"
else
  echo "El scheduler no arrancó correctamente"
  exit 1
fi
