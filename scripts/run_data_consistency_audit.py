from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.data_consistency_audit import (  # noqa: E402
    format_data_consistency_audit,
    run_data_consistency_audit,
    write_data_consistency_audit,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run-data-consistency-audit")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reports_path = Path(args.reports_path)
    result = run_data_consistency_audit(data_path=Path(args.data_path), reports_path=reports_path)
    print(format_data_consistency_audit(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_data_consistency_audit(result, reports_path)
    print(f"JSON: {paths['json_path']}")
    print(f"Markdown: {paths['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
