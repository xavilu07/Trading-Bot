#!/usr/bin/env bash
set -euo pipefail

# Install an hourly cron job to regenerate the local dashboard.
# Intended for the Ubuntu VPS. Run from anywhere:
#   bash scripts/install_dashboard_cron.sh

APP_DIR="${APP_DIR:-/root/bot}"
CRON_MARKER="# trading-bot-dashboard-refresh"
LOG_FILE="$APP_DIR/logs/dashboard_refresh.log"
CRON_JOB="0 * * * * TZ=Europe/Madrid cd $APP_DIR && . .venv/bin/activate && python scripts/generate_dashboard.py --min-trades 3 >> $LOG_FILE 2>&1 $CRON_MARKER"

echo "========================================"
echo " Install Dashboard Refresh cron"
echo "========================================"
echo "App dir: $APP_DIR"
echo "Timezone: Europe/Madrid"
echo "Schedule: every 1 hour"
echo "Log file: $LOG_FILE"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: app directory not found: $APP_DIR"
  exit 1
fi

mkdir -p "$APP_DIR/logs"

TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

# Preserve existing crontab entries and replace only this dashboard job.
crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" > "$TMP_CRON" || true
printf "%s\n" "$CRON_JOB" >> "$TMP_CRON"
crontab "$TMP_CRON"

echo
echo "Cron installed without duplicates."
echo
echo "Current matching cron:"
crontab -l | grep -F "$CRON_MARKER" || true

