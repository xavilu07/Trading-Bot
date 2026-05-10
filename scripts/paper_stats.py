from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_signals.application.use_cases.paper_stats import (
    build_paper_performance_summary,
    format_paper_performance_summary,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="paper-stats")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_paper_performance_summary(Path(args.data_path))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_paper_performance_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
