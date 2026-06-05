from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.score_80_89_regime_decomposition import (  # noqa: E402
    analyze_score_80_89_regime_decomposition,
    write_score_80_89_regime_decomposition_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="score-80-89-regime-decomposition")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_score_80_89_regime_decomposition(data_path=Path(args.data_path))
    report_path = write_score_80_89_regime_decomposition_report(result, Path(args.reports_path))
    metrics = result["metrics"]
    answers = result["answers"]
    print("SCORE_80_89_REGIME_DECOMPOSITION")
    print(f"- TRENDING: {metrics['trending']}")
    print(f"- RANGING: {metrics['ranging']}")
    print(f"- Toxic TRENDING subgroups: {len(result['toxic_trending_subgroups'])}")
    print(f"- Safe RANGING survivors: {len(result['safe_ranging_survivors'])}")
    print(f"- Main difference subgroup: {answers['main_difference_subgroup']}")
    print(f"- Next investigation: {result['next_recommended_investigation']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
