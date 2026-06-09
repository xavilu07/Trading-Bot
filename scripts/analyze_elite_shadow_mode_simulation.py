from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.elite_shadow_mode_simulation import (  # noqa: E402
    analyze_elite_shadow_mode_simulation,
    write_elite_shadow_mode_simulation_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="elite-shadow-mode-simulation")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_elite_shadow_mode_simulation(data_path=Path(args.data_path))
    paths = write_elite_shadow_mode_simulation_reports(result, Path(args.reports_path))
    baseline = result["baseline_after_production_blocks"]
    answers = result["answers"]
    print("ELITE_SHADOW_MODE_SIMULATION")
    print(f"- Baseline after blocks: trades={baseline['trades']} | WR={baseline['winrate']}% | PF={baseline['profit_factor']} | TotalR={baseline['total_r']}")
    print(f"- Max PF profile: {answers['max_pf_profile']}")
    print(f"- Max TotalR profile: {answers['max_total_r_profile']}")
    print(f"- Best enough-trades profile: {answers['best_pf_enough_trades_profile']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
