from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.london_short_edge_attribution import (  # noqa: E402
    analyze_london_short_edge_attribution,
    format_london_short_edge_attribution,
    load_london_short_research_rows,
    write_london_short_edge_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="analyze-london-short-edge-attribution")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    reports_path = Path(args.reports_path)
    rows = load_london_short_research_rows(data_path, reports_path)
    result = analyze_london_short_edge_attribution(rows, min_trades=max(1, args.min_trades))
    print(format_london_short_edge_attribution(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_london_short_edge_reports(result, reports_path)
    print(f"JSON: {paths['json_path']}")
    print(f"CSV: {paths['csv_path']}")
    print(f"Summary: {paths['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
