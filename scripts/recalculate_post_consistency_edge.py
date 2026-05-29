from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.post_consistency_edge import (  # noqa: E402
    format_post_consistency_edge_summary,
    recalculate_post_consistency_edge,
    write_post_consistency_edge_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="recalculate-post-consistency-edge")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = recalculate_post_consistency_edge(data_path=Path(args.data_path), min_trades=max(1, args.min_trades))
    print(format_post_consistency_edge_summary(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_post_consistency_edge_reports(result, Path(args.reports_path))
    print(f"JSON: {paths['json_path']}")
    print(f"CSV: {paths['csv_path']}")
    print(f"Summary: {paths['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
