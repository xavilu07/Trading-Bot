from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.modular_paper import ModularSignalStore
from trading_signals.infrastructure.exchange.provider_factory import build_market_data_provider


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="update-modular-outcomes")
    parser.add_argument("--data-path", default="")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--win-threshold", type=float, default=0.015)
    parser.add_argument("--loss-threshold", type=float, default=0.01)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    data_path = Path(args.data_path) if args.data_path else settings.data_storage_path
    market_data = build_market_data_provider(settings)
    store = ModularSignalStore(data_path)
    updated = store.update_pending_outcomes(
        market_data,
        interval=args.interval,
        limit=args.limit,
        win_threshold=args.win_threshold,
        loss_threshold=args.loss_threshold,
    )
    print(f"Modular outcomes updated: {len(updated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
