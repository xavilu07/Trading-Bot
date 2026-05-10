#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.runtime/experimental_outcomes.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Experimental outcomes scheduler parado"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Experimental outcomes scheduler activo con PID $PID"
else
  rm -f "$PID_FILE"
  echo "Experimental outcomes scheduler parado"
fi

