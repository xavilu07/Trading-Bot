#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$ROOT_DIR/.runtime/scheduler.log"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "No hay logs todavía"
  exit 0
fi

tail -n 100 "$LOG_FILE"
