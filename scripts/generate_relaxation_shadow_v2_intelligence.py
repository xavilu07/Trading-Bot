from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.application.use_cases.relaxation_shadow_v2 import (  # noqa: E402
    build_relaxation_shadow_v2_intelligence,
    format_relaxation_shadow_v2_markdown,
    write_relaxation_shadow_v2_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-relaxation-shadow-v2-intelligence")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-trades", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_relaxation_shadow_v2_intelligence(
        data_path=Path(args.data_path),
        min_trades=max(1, args.min_trades),
    )
    print(format_relaxation_shadow_v2_markdown(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_relaxation_shadow_v2_reports(result, Path(args.reports_path))
    print(f"Markdown: {paths['markdown_path']}")
    print(f"JSON: {paths['json_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
