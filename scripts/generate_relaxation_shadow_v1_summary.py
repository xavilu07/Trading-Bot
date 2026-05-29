from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.application.use_cases.relaxation_shadow_v1 import (  # noqa: E402
    build_relaxation_shadow_summary,
    format_relaxation_shadow_summary,
    write_relaxation_shadow_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-relaxation-shadow-v1-summary")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_relaxation_shadow_summary(Path(args.data_path))
    print(format_relaxation_shadow_summary(summary))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_relaxation_shadow_reports(Path(args.data_path), Path(args.reports_path))
    print(f"Summary: {paths['summary_md']}")
    print(f"Trades CSV: {paths['trades_csv']}")
    print(f"Summary CSV: {paths['summary_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
