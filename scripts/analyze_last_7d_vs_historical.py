from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.last_7d_vs_historical_analysis import (  # noqa: E402
    analyze_last_7d_vs_historical,
    audit_last_7d_data_sources,
    write_last_7d_data_source_audit,
    write_last_7d_vs_historical_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="last-7d-vs-historical-analysis")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--now", default="", help="Optional ISO timestamp used as analysis anchor.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(UTC) if args.now else None
    result = analyze_last_7d_vs_historical(data_path=Path(args.data_path), now=now)
    report_path = write_last_7d_vs_historical_report(result, Path(args.reports_path))
    audit = audit_last_7d_data_sources(data_path=Path(args.data_path), reports_path=Path(args.reports_path), now=now)
    audit_path = write_last_7d_data_source_audit(audit, Path(args.reports_path))
    periods = result["periods"]
    short = result["direction_comparison"]["short"]
    long = result["direction_comparison"]["long"]
    shift = result["regime_shift_detection"]
    print("LAST_7D_VS_HISTORICAL_REGIME_ANALYSIS")
    print(f"- Last 7d trades: {periods['last_7d']['metrics']['total_trades']} | Total R: {periods['last_7d']['metrics']['total_r']} | PF: {periods['last_7d']['metrics']['profit_factor']}")
    print(f"- Last 30d trades: {periods['last_30d']['metrics']['total_trades']} | Total R: {periods['last_30d']['metrics']['total_r']} | PF: {periods['last_30d']['metrics']['profit_factor']}")
    print(f"- Full trades: {periods['full_history']['metrics']['total_trades']} | Total R: {periods['full_history']['metrics']['total_r']} | PF: {periods['full_history']['metrics']['profit_factor']}")
    print(f"- SHORT classification: {short['classification']}")
    print(f"- LONG classification: {long['classification']}")
    print(f"- Regime shift: {shift['classification']} | material={shift['material_difference']}")
    print(f"- Recommended action: {result['executive_summary']['recommended_action']}")
    print(f"- Report: {report_path}")
    print(f"- Data source audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
