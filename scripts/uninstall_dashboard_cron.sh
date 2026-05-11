#!/usr/bin/env bash
set -euo pipefail

# Remove the hourly dashboard refresh cron job.
# Intended for the Ubuntu VPS. Run from anywhere:
#   bash scripts/uninstall_dashboard_cron.sh

CRON_MARKER="# trading-bot-dashboard-refresh"

echo "========================================"
echo " Uninstall Dashboard Refresh cron"
echo "========================================"

TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

crontab -l 2>/dev/null | grep -vF "$CRON_MARKER" > "$TMP_CRON" || true
crontab "$TMP_CRON"

echo "Cron removed."
echo
echo "Current matching cron:"
crontab -l 2>/dev/null | grep -F "$CRON_MARKER" || echo "No dashboard refresh cron installed."

