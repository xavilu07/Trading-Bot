from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.memory.insights import build_pattern_memory_insights


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_bot_status(*, base_path: Path, settings) -> dict[str, object]:
    patterns_path = base_path / "data" / "pattern_memory" / "patterns.jsonl"
    scheduler_log = base_path / "logs" / "scheduler.log"
    pattern_records = _read_jsonl(patterns_path)
    insights = build_pattern_memory_insights(pattern_records)
    return {
        "telegram": {
            "bot_token_configured": bool(settings.telegram_bot_token),
            "public_chat_configured": bool(settings.telegram_public_chat_id),
            "dev_chat_configured": bool(settings.telegram_dev_chat_id),
        },
        "pattern_memory": {
            "path": str(patterns_path),
            "exists": patterns_path.exists(),
            "records": len(pattern_records),
            "size_bytes": _file_size(patterns_path),
            "insights_ready": bool(insights.get("has_sufficient_data")),
        },
        "logs": {
            "scheduler_log_path": str(scheduler_log),
            "scheduler_log_exists": scheduler_log.exists(),
            "scheduler_log_size_bytes": _file_size(scheduler_log),
            "scheduler_log_updated_at": _mtime_iso(scheduler_log),
        },
        "runtime": {
            "environment_loaded": True,
            "scheduler_expected_interval_seconds": settings.scan_interval_seconds,
        },
    }


def format_bot_status(status: dict[str, object]) -> str:
    telegram = _dict(status.get("telegram"))
    memory = _dict(status.get("pattern_memory"))
    logs = _dict(status.get("logs"))
    runtime = _dict(status.get("runtime"))
    telegram_ok = all(
        bool(telegram.get(key))
        for key in ("bot_token_configured", "public_chat_configured", "dev_chat_configured")
    )
    return (
        f"{_mark(True)} Bot status\n"
        f"{_mark(telegram_ok)} Telegram configured\n"
        f"{_mark(telegram.get('public_chat_configured'))} Public channel configured\n"
        f"{_mark(telegram.get('dev_chat_configured'))} DEV channel configured\n\n"
        "🧠 Pattern Memory\n"
        f"- Patterns stored: {memory.get('records', 0)}\n"
        f"- Insights ready: {_yes_no(memory.get('insights_ready'))}\n"
        f"- File size: {_format_size(int(memory.get('size_bytes', 0)))}\n\n"
        "📄 Logs\n"
        f"- Scheduler log: {'OK' if logs.get('scheduler_log_exists') else 'MISSING'}\n"
        f"- Size: {_format_size(int(logs.get('scheduler_log_size_bytes', 0)))}\n"
        f"- Last update: {logs.get('scheduler_log_updated_at') or 'unknown'}\n\n"
        "⚙️ Runtime\n"
        f"- Environment loaded: {_yes_no(runtime.get('environment_loaded'))}\n"
        f"- Scheduler expected interval: {runtime.get('scheduler_expected_interval_seconds', '-')} sec"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bot-status")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--base-path", default=".")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_path = Path(args.base_path)
    load_dotenv(base_path / args.env_file)
    settings = load_settings()
    status = build_bot_status(base_path=base_path, settings=settings)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(format_bot_status(status))
    return 0


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / 1024:.2f} KB"


def _mark(value: object) -> str:
    return "✅" if bool(value) else "❌"


def _yes_no(value: object) -> str:
    return "YES" if bool(value) else "NO"


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
