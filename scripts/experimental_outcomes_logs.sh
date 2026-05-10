#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$ROOT_DIR/.runtime/experimental_outcomes.log"

touch "$LOG_FILE"
tail -f "$LOG_FILE"
