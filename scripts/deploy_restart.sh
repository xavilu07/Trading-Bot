#!/usr/bin/env bash
set -euo pipefail

# Deploy/restart script for the VPS.
# Run from anywhere on the VPS with:
#   bash scripts/deploy_restart.sh

APP_DIR="/root/bot"
SCREEN_NAME="trading-bot"
SCHEDULER_PATTERN="python -m trading_signals.app.cli scheduler"

python_scheduler_processes() {
  ps -eo pid,args \
    | awk '
      NR == 1 { next }
      {
        pid = $1
        $1 = ""
        sub(/^[[:space:]]+/, "", $0)
        args = $0

        is_python = args ~ /(^|\/)python([0-9]+([.][0-9]+)?)?([[:space:]]|$)/
        is_scheduler = args ~ /(^|[[:space:]])-m[[:space:]]+trading_signals[.]app[.]cli[[:space:]]+scheduler([[:space:]]|$)/
        is_wrapper = args ~ /(^|[[:space:]])(SCREEN|bash|sh|zsh|grep)([[:space:]]|$)/

        if (is_python && is_scheduler && !is_wrapper) {
          print pid " " args
        }
      }
    '
}

echo "========================================"
echo " Trading bot deploy/restart"
echo "========================================"
cd "$APP_DIR"

echo
echo "[1/7] Updating repository"
git pull

echo
echo "[2/7] Activating virtualenv"
source .venv/bin/activate

echo
echo "[3/7] Loading environment"
if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in $APP_DIR"
  exit 1
fi
set -a
source .env
set +a

echo
echo "[4/7] Installing package"
pip install -e .

echo
echo "[5/7] Stopping existing screen session if present"
if command -v screen >/dev/null 2>&1; then
  if screen -list | grep -q "[.]${SCREEN_NAME}[[:space:]]"; then
    screen -S "$SCREEN_NAME" -X quit || true
    sleep 2
  fi
else
  echo "ERROR: screen is not installed"
  exit 1
fi

echo
echo "[6/7] Killing duplicated scheduler processes"
pkill -f "$SCHEDULER_PATTERN" || true
sleep 2
if pgrep -f "$SCHEDULER_PATTERN" >/dev/null 2>&1; then
  pkill -9 -f "$SCHEDULER_PATTERN" || true
  sleep 1
fi

mkdir -p logs

echo
echo "[7/7] Starting scheduler in screen: $SCREEN_NAME"
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

SCHEDULER_PID="$(printf "%s\n" "$PROCESS_LIST" | awk 'NF { print $1; exit }')"

echo
echo "========================================"
echo " Final status"
echo "========================================"
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

echo "Scheduler PID: $SCHEDULER_PID"
echo "Scheduler status: OK"
echo
echo "Active screen sessions:"
screen -list || true
echo
echo "Scheduler process:"
printf "%s\n" "$PROCESS_LIST"
echo
echo "Last 3 scheduler logs:"
if [[ -f "logs/scheduler.log" ]]; then
  tail -n 3 logs/scheduler.log
else
  echo "logs/scheduler.log not found yet"
fi
