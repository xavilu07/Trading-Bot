from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.bot_audit_ai import (  # noqa: E402
    format_bot_audit_ai_markdown,
    generate_bot_audit_ai,
    write_bot_audit_ai,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-bot-audit-ai")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_bot_audit_ai(data_path=Path(args.data_path), reports_path=Path(args.reports_path))
    print(format_bot_audit_ai_markdown(result))
    if args.dry_run:
        print("Dry-run: reports were not written.")
        return 0
    paths = write_bot_audit_ai(result, Path(args.reports_path))
    print(f"Markdown: {paths['markdown_path']}")
    print(f"JSON: {paths['json_path']}")
    print(f"Inputs audit: {paths['inputs_audit_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
