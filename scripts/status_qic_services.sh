#!/usr/bin/env bash
set -euo pipefail

systemctl --no-pager --full status qic-telegram-listener.service || true
systemctl --no-pager --full list-timers 'qic-*' || true
systemctl --no-pager --full list-units 'qic-*' || true
