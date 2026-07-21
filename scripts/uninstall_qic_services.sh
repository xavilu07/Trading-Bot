#!/usr/bin/env bash
set -euo pipefail

SYSTEMD_DIR="${QIC_SYSTEMD_DIR:-/etc/systemd/system}"
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

systemctl disable --now "${units[@]}" 2>/dev/null || true
for unit in "${units[@]}"; do
  if [[ -f "$SYSTEMD_DIR/$unit" ]]; then
    unlink "$SYSTEMD_DIR/$unit"
  fi
done
systemctl daemon-reload
echo "QIC units removed. Runtime data and configuration were preserved."
