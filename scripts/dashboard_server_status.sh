#!/usr/bin/env bash
set -euo pipefail

# Show whether the local dashboard HTTP server is listening on port 8090.
# This is a read-only status check.

APP_DIR="${APP_DIR:-/root/bot}"
PORT="${DASHBOARD_PORT:-8090}"
PID_FILE="$APP_DIR/logs/dashboard_server.pid"

echo "========================================"
echo " Dashboard local server status"
echo "========================================"
echo "Port: $PORT"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$PID" ]] && ps -p "$PID" >/dev/null 2>&1; then
    echo "PID file: $PID_FILE"
    echo "Process status: RUNNING"
    echo "PID: $PID"
  else
    echo "PID file exists, but process is not running."
  fi
else
  echo "PID file: missing"
fi

if command -v lsof >/dev/null 2>&1; then
  if lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "Port status: ACTIVE"
    lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P
  else
    echo "Port status: INACTIVE"
  fi
else
  echo "Port status: cannot check with lsof; lsof is not installed"
fi

