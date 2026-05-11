#!/usr/bin/env bash
set -euo pipefail

# Deploy/restart script for the VPS.
# Run from anywhere on the VPS with:
#   bash scripts/deploy_restart.sh

APP_DIR="/root/bot"
SCREEN_NAME="trading-bot"
SCHEDULER_PATTERN="python -m trading_signals.app.cli scheduler"

python_scheduler_processes() {
  ps -eo pid=,args= \
    | awk '
      /(^|\/)python[0-9.]* .* -m trading_signals[.]app[.]cli scheduler/ &&
      $0 !~ /SCREEN/ &&
      $0 !~ /bash -lc/ &&
      $0 !~ /grep/ {
        print
      }
    '
}

echo "== Trading bot deploy/restart =="
cd "$APP_DIR"

echo "== Updating repository =="
git pull

echo "== Activating virtualenv =="
source .venv/bin/activate

echo "== Loading environment =="
if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in $APP_DIR"
  exit 1
fi
set -a
source .env
set +a

echo "== Installing package =="
pip install -e .

echo "== Stopping existing screen session if present =="
if command -v screen >/dev/null 2>&1; then
  if screen -list | grep -q "[.]${SCREEN_NAME}[[:space:]]"; then
    screen -S "$SCREEN_NAME" -X quit || true
    sleep 2
  fi
else
  echo "ERROR: screen is not installed"
  exit 1
fi

echo "== Killing duplicated scheduler processes =="
pkill -f "$SCHEDULER_PATTERN" || true
sleep 2
if pgrep -f "$SCHEDULER_PATTERN" >/dev/null 2>&1; then
  pkill -9 -f "$SCHEDULER_PATTERN" || true
  sleep 1
fi

mkdir -p logs

echo "== Starting scheduler in screen: $SCREEN_NAME =="
screen -dmS "$SCREEN_NAME" bash -lc '
  cd /root/bot
  source .venv/bin/activate
  set -a
  source .env
  set +a
  exec python -m trading_signals.app.cli scheduler >> logs/scheduler.log 2>&1
'

sleep 3

PROCESS_LIST="$(python_scheduler_processes || true)"
PROCESS_COUNT="$(printf "%s\n" "$PROCESS_LIST" | sed '/^[[:space:]]*$/d' | wc -l | tr -d ' ')"
SCREEN_ACTIVE="NO"
if screen -list | grep -q "[.]${SCREEN_NAME}[[:space:]]"; then
  SCREEN_ACTIVE="YES"
fi

echo "== Final status =="
echo "App dir: $APP_DIR"
echo "Screen session: $SCREEN_NAME"
echo "Screen active: $SCREEN_ACTIVE"
echo "Scheduler processes: $PROCESS_COUNT"

if [[ "$PROCESS_COUNT" != "1" ]]; then
  echo "ERROR: expected exactly 1 scheduler process, found $PROCESS_COUNT"
  echo "Matching processes:"
  printf "%s\n" "$PROCESS_LIST"
  exit 1
fi

echo "OK: scheduler restarted successfully"
printf "%s\n" "$PROCESS_LIST"
