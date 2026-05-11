#!/usr/bin/env bash
set -euo pipefail

# Serve reports/ locally on the VPS so it can be accessed safely through SSH tunneling.
# Start on the VPS:
#   bash scripts/dashboard_server.sh
#
# Open from your Mac:
#   ssh -L 8090:127.0.0.1:8090 root@82.223.151.12
#   http://localhost:8090/dashboard.html

APP_DIR="${APP_DIR:-/root/bot}"
PORT="${DASHBOARD_PORT:-8090}"
HOST="127.0.0.1"
PID_FILE="$APP_DIR/logs/dashboard_server.pid"
LOG_FILE="$APP_DIR/logs/dashboard_server.log"

echo "========================================"
echo " Dashboard local server"
echo "========================================"
echo "App dir: $APP_DIR"
echo "Bind: $HOST:$PORT"
echo "Directory: $APP_DIR/reports"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: app directory not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
mkdir -p logs reports

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && ps -p "$OLD_PID" >/dev/null 2>&1; then
    echo "Dashboard server already running. PID: $OLD_PID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P | grep -q "$HOST:$PORT"; then
  echo "ERROR: port $PORT is already listening on $HOST"
  lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P
  exit 1
fi

nohup python -m http.server "$PORT" --bind "$HOST" --directory reports >> "$LOG_FILE" 2>&1 &
SERVER_PID="$!"
echo "$SERVER_PID" > "$PID_FILE"
sleep 1

if ps -p "$SERVER_PID" >/dev/null 2>&1; then
  echo "Dashboard server status: OK"
  echo "PID: $SERVER_PID"
  echo "URL through SSH tunnel: http://localhost:$PORT/dashboard.html"
  echo "Log: $LOG_FILE"
else
  echo "ERROR: dashboard server failed to start"
  rm -f "$PID_FILE"
  tail -n 20 "$LOG_FILE" 2>/dev/null || true
  exit 1
fi

