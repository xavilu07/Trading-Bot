from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.elite_profile_c_dna_expansion import (  # noqa: E402
    analyze_elite_profile_c_dna_expansion,
    write_elite_profile_c_dna_expansion_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="elite-profile-c-dna-expansion")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_elite_profile_c_dna_expansion(data_path=Path(args.data_path))
    paths = write_elite_profile_c_dna_expansion_reports(result, Path(args.reports_path))
    baseline = result["baseline"]
    final = result["final_answer"]
    print("ELITE_PROFILE_C_DNA_EXPANSION")
    print(f"- Profile C trades: {baseline['trades']}")
    print(f"- WR: {baseline['winrate']}% | PF: {baseline['profit_factor']} | TotalR: {baseline['total_r']} | AvgR: {baseline['avg_r']}")
    print(f"- Strongest elite DNA: {final['strongest_elite_dna']}")
    print(f"- Safest elite DNA: {final['safest_elite_dna']}")
    print(f"- Highest PF elite DNA: {final['highest_pf_elite_dna']}")
    print(f"- Highest TotalR elite DNA: {final['highest_total_r_elite_dna']}")
    print(f"- Recommendation: {result['recommendation']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
