#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.active_signal_cleanup_v1 import (
    ActiveSignalCleanupConfig,
    run_active_signal_cleanup_v1,
    write_active_signal_cleanup_v1_design_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Manual ACTIVE_SIGNAL_CLEANUP_V1 runner.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Detect zombies without modifying files.")
    mode.add_argument("--apply", action="store_true", help="Apply cleanup manually and create backups first.")
    parser.add_argument("--data-path", type=Path, default=None)
    parser.add_argument("--reports-path", type=Path, default=root / "reports")
    parser.add_argument("--zombie-hours", type=float, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    manual_mode = args.dry_run or args.apply
    enabled = True if manual_mode else settings.active_signal_cleanup_enabled
    dry_run = True if args.dry_run else (False if args.apply else settings.active_signal_cleanup_dry_run)
    data_path = args.data_path or settings.data_storage_path
    zombie_hours = args.zombie_hours if args.zombie_hours is not None else settings.active_signal_cleanup_zombie_hours
    config = ActiveSignalCleanupConfig(enabled=enabled, dry_run=dry_run, zombie_hours=zombie_hours)
    result = run_active_signal_cleanup_v1(data_path=data_path, config=config)
    design_path = write_active_signal_cleanup_v1_design_report(args.reports_path)

    for event in result.events:
        print(json.dumps(event, sort_keys=True))
    print("ACTIVE_SIGNAL_CLEANUP_V1")
    print(f"- enabled: {result.enabled}")
    print(f"- dry_run: {result.dry_run}")
    print(f"- scanned: {result.scanned}")
    print(f"- candidates: {len(result.candidates)}")
    print(f"- closed: {len(result.closed)}")
    print(f"- backup_dir: {result.backup_dir}")
    print(f"- design_report: {design_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
