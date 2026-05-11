#!/usr/bin/env bash
set -euo pipefail

# Install a daily cron job for the DEV Telegram report.
# Intended for the Ubuntu VPS. Run from anywhere:
#   bash scripts/install_daily_dev_report_cron.sh

APP_DIR="${APP_DIR:-/root/bot}"
CRON_MARKER="# trading-bot-daily-dev-report"
LOG_FILE="$APP_DIR/logs/daily_dev_report.log"
CRON_JOB="0 9 * * * TZ=Europe/Madrid cd $APP_DIR && . .venv/bin/activate && python scripts/send_daily_dev_report.py >> $LOG_FILE 2>&1 $CRON_MARKER"

echo "========================================"
echo " Install Daily DEV Report cron"
echo "========================================"
echo "App dir: $APP_DIR"
echo "Timezone: Europe/Madrid"
echo "Schedule: daily at 09:00"
echo "Log file: $LOG_FILE"

if [[ ! -d "$APP_DIR" ]]; then
  echo "ERROR: app directory not found: $APP_DIR"
  exit 1
fi

mkdir -p "$APP_DIR/logs"

TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

# Keep existing crontab entries, but remove previous versions of this job first.
crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" > "$TMP_CRON" || true
printf "%s\n" "$CRON_JOB" >> "$TMP_CRON"
crontab "$TMP_CRON"

echo
echo "Cron installed without duplicates."
echo
echo "Current matching cron:"
crontab -l | grep -F "$CRON_MARKER" || true

