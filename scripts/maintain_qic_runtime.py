from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.agents.qic_runtime import atomic_write_json, utc_now
from trading_signals.app.settings import load_settings


def maintain_qic_runtime(
    *,
    data_path: Path = Path("data") / "qic",
    logs_path: Path = Path("logs"),
    backup_root: Path = Path("data") / "qic_backups",
    retention_days: int = 90,
    dry_run: bool = False,
) -> dict[str, object]:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_root / stamp
    copied = []
    if data_path.exists() and not dry_run:
        shutil.copytree(data_path, backup_path, dirs_exist_ok=False)
        copied.append(str(backup_path))
    cutoff = datetime.now(tz=UTC) - timedelta(days=max(1, retention_days))
    rotation_candidates = []
    for root in (backup_root, logs_path):
        if not root.exists():
            continue
        for path in root.iterdir():
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified < cutoff and (path.name.startswith("qic") or root == backup_root):
                rotation_candidates.append(path)
    removed = []
    if not dry_run:
        for path in rotation_candidates:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(str(path))
    report = {
        "generated_at": utc_now(),
        "dry_run": dry_run,
        "backup_created": copied,
        "rotation_candidates": [str(item) for item in rotation_candidates],
        "removed": removed,
        "retention_days": retention_days,
    }
    atomic_write_json(Path("reports") / "qic" / "maintenance.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up and rotate QIC runtime artifacts.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    settings = load_settings()
    report = maintain_qic_runtime(retention_days=int(getattr(settings, "qic_report_retention_days", 90)), dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
