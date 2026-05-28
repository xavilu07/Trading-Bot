from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.strategy_validation import (  # noqa: E402
    format_strategy_validation_summary,
    load_strategy_validation_records,
    run_strategy_validation,
    write_strategy_validation_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run-strategy-validation")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--rolling-window", type=int, default=100)
    parser.add_argument("--delay-candles", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    reports_path = Path(args.reports_path)
    records = load_strategy_validation_records(data_path, reports_path)
    result = run_strategy_validation(
        records,
        rolling_window=max(1, args.rolling_window),
        delay_candles=max(0, args.delay_candles),
    )
    print(format_strategy_validation_summary(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_strategy_validation_reports(result, reports_path)
    print(f"JSON: {paths['json_path']}")
    print(f"Summary: {paths['summary_path']}")
    print(f"Matrix: {paths['matrix_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
