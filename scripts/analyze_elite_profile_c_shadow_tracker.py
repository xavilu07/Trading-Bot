from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.elite_profile_c_shadow_tracker import generate_elite_profile_c_shadow_tracker  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="elite-profile-c-shadow-tracker")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--dev-note-enabled", action="store_true", default=_env_bool("ELITE_PROFILE_C_DEV_NOTE_ENABLED", False))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_elite_profile_c_shadow_tracker(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        dev_note_enabled=bool(args.dev_note_enabled),
    )
    metrics = result["metrics"]
    print("ELITE_PROFILE_C_SHADOW_TRACKER")
    print(f"- Total tracked: {result['total_tracked']}")
    print(f"- Closed/evaluable: {result['closed_evaluable']}")
    print(f"- WR: {metrics['winrate']}% | PF: {metrics['profit_factor']} | TotalR: {metrics['total_r']} | AvgR: {metrics['avg_r']}")
    print(f"- Recommendation: {result['recommendation']}")
    print(f"- CSV: {result['shadow_csv_path']}")
    print(f"- Report: {result['report_path']}")
    return 0


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
