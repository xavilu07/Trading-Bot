#!/usr/bin/env bash
set -euo pipefail
cd /root/bot
export DEPLOYMENT_ID="main-$(git rev-parse --short HEAD)-$(date +%Y-%m-%d)"
exec .venv/bin/python scripts/run_scheduler.py
