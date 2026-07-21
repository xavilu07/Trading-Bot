#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${QIC_APP_DIR:-/root/bot}"
SYSTEMD_DIR="${QIC_SYSTEMD_DIR:-/etc/systemd/system}"
SOURCE_DIR="$APP_DIR/deploy/systemd"
ENABLE_UNITS=false
if [[ "${1:-}" == "--enable" ]]; then
  ENABLE_UNITS=true
elif [[ -n "${1:-}" ]]; then
  echo "Usage: $0 [--enable]" >&2
  exit 2
fi

if [[ ! -d "$APP_DIR" || ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "QIC install aborted: missing app directory or virtualenv at $APP_DIR" >&2
  exit 1
fi

units=(
  qic-telegram-listener.service
  qic-autonomous.service qic-autonomous.timer
  qic-events.service qic-events.timer
  qic-revalidation.service qic-revalidation.timer
  qic-health.service qic-health.timer
  qic-daily-report.service qic-daily-report.timer
  qic-weekly-report.service qic-weekly-report.timer
  qic-maintenance.service qic-maintenance.timer
)

for unit in "${units[@]}"; do
  install -m 0644 "$SOURCE_DIR/$unit" "$SYSTEMD_DIR/$unit"
done

systemctl daemon-reload
if [[ "$ENABLE_UNITS" == "true" ]]; then
  systemctl enable qic-telegram-listener.service
  systemctl enable qic-autonomous.timer qic-events.timer qic-revalidation.timer qic-health.timer
  systemctl enable qic-daily-report.timer qic-weekly-report.timer qic-maintenance.timer
fi

echo "QIC units installed. enabled=$ENABLE_UNITS. No trading service was changed and no QIC unit was started."
echo "Enable explicitly with: $0 --enable"
echo "Start explicitly with: systemctl start qic-telegram-listener qic-autonomous.timer qic-events.timer qic-revalidation.timer qic-health.timer qic-daily-report.timer qic-weekly-report.timer qic-maintenance.timer"
