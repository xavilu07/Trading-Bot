from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="experimental-outcomes-scheduler")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    interval = max(60, args.interval_seconds)
    script = Path(__file__).with_name("update_experimental_outcomes.py")
    while True:
        started_at = datetime.now(tz=UTC).isoformat()
        print(f'{{"event":"experimental_outcomes_scheduler_cycle","started_at":"{started_at}","interval_seconds":{interval}}}', flush=True)
        result = subprocess.run(
            [sys.executable, str(script)],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.stdout:
            print(result.stdout.strip(), flush=True)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr, flush=True)
        if result.returncode != 0:
            print(
                f'{{"event":"experimental_outcomes_scheduler_error","returncode":{result.returncode}}}',
                file=sys.stderr,
                flush=True,
            )
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
