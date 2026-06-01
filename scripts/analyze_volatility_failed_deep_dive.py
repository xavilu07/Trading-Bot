from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.volatility_failed_deep_dive import (  # noqa: E402
    analyze_volatility_failed_deep_dive,
    write_volatility_failed_deep_dive_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="volatility-failed-deep-dive")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_volatility_failed_deep_dive(data_path=Path(args.data_path))
    report_path = write_volatility_failed_deep_dive_report(result, Path(args.reports_path))
    metrics = result["metrics"]
    baseline = result["canonical_baseline"]["metrics"]
    accepted = result["accepted_trades"]["metrics"]
    print("VOLATILITY_FAILED_DEEP_DIVE")
    print(f"- Count: {result['count']}")
    print(f"- Closed: {metrics['closed']}")
    print(f"- WR: {metrics['winrate']}%")
    print(f"- PF: {metrics['profit_factor']}")
    print(f"- Total R: {metrics['total_r']}")
    print(f"- Avg R: {metrics['avg_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Accepted trades: {result['accepted_trades']['count']} | Total R: {accepted['total_r']} | PF: {accepted['profit_factor']}")
    print(f"- Canonical baseline: {result['canonical_baseline']['count']} | Total R: {baseline['total_r']} | PF: {baseline['profit_factor']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
