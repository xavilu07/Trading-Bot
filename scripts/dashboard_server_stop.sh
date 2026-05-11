#!/usr/bin/env bash
set -euo pipefail

# Stop the local dashboard HTTP server if it is running.
# This only stops the reports/ static server, not the trading bot scheduler.

APP_DIR="${APP_DIR:-/root/bot}"
PORT="${DASHBOARD_PORT:-8090}"
PID_FILE="$APP_DIR/logs/dashboard_server.pid"

echo "========================================"
echo " Stop dashboard local server"
echo "========================================"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID" ]] && ps -p "$PID" >/dev/null 2>&1; then
    kill "$PID"
    sleep 1
    if ps -p "$PID" >/dev/null 2>&1; then
      kill -9 "$PID" || true
    fi
    echo "Stopped dashboard server PID: $PID"
  else
    echo "PID file found, but process is not running."
  fi
  rm -f "$PID_FILE"
else
  echo "No PID file found."
fi

if command -v lsof >/dev/null 2>&1; then
  MATCHES="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN -n -P 2>/dev/null || true)"
  if [[ -n "$MATCHES" ]]; then
    echo "Stopping remaining listeners on port $PORT:"
    echo "$MATCHES"
    kill $MATCHES || true
  fi
fi

echo "Dashboard server stopped if it was running."

