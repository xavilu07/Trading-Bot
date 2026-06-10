from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.elite_subprofile_shadow_tracker import (  # noqa: E402
    analyze_elite_subprofile_shadow_tracker,
    write_elite_subprofile_shadow_tracker_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="elite-subprofile-shadow-tracker")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_elite_subprofile_shadow_tracker(data_path=Path(args.data_path))
    paths = write_elite_subprofile_shadow_tracker_reports(result, Path(args.reports_path))
    baseline = result["elite_profile_c_baseline"]
    print("ELITE_SUBPROFILE_SHADOW_TRACKER")
    print(f"- Elite C baseline: trades={baseline['trades']} | WR={baseline['winrate']}% | PF={baseline['profit_factor']} | TotalR={baseline['total_r']}")
    for profile in result["profiles"]:
        metrics = profile["metrics"]
        deltas = profile["deltas_vs_elite_c"]
        print(
            f"- {profile['profile']}: tracked={profile['tracked']} | WR={metrics['winrate']}% | PF={metrics['profit_factor']} | "
            f"TotalR={metrics['total_r']} | PF delta={deltas['pf_delta']} | WR delta={deltas['wr_delta']} | "
            f"R delta={deltas['total_r_delta']} | recommendation={profile['recommendation']}"
        )
    print(f"- Recommendation summary: {result['recommendation_summary']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
