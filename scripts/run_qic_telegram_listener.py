from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.qic_telegram_config import load_qic_telegram_config
from trading_signals.agents.telegram_approval import poll_approval_callbacks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run persistent QIC Telegram callback listener.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--reports-path", type=Path, default=Path("reports") / "qic")
    args = parser.parse_args(argv)

    config = load_qic_telegram_config()
    if not config["configured"]:
        report = _listener_report(
            running=False,
            callbacks_processed=0,
            last_callback=None,
            errors=["qic_telegram_not_configured"],
            reports_path=args.reports_path,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    total_processed = 0
    errors: list[str] = []
    last_callback = None
    while True:
        result = poll_approval_callbacks(
            bot_token=str(config["bot_token"]),
            limit=args.limit,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        processed = result.get("processed") if isinstance(result.get("processed"), list) else []
        total_processed += len(processed)
        if processed:
            last_callback = processed[-1]
        if result.get("status") not in {"ok", "dry_run"}:
            errors.append(str(result.get("error_message") or result.get("reason") or result.get("status")))
        report = _listener_report(
            running=not args.once,
            callbacks_processed=total_processed,
            last_callback=last_callback,
            errors=errors[-20:],
            reports_path=args.reports_path,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.once:
            return 0 if result.get("status") in {"ok", "dry_run"} else 1
        time.sleep(max(args.poll_interval, 1.0))


def _listener_report(
    *,
    running: bool,
    callbacks_processed: int,
    last_callback: dict[str, Any] | None,
    errors: list[str],
    reports_path: Path,
) -> dict[str, Any]:
    payload = {
        "running": running,
        "last_update": datetime.now(tz=UTC).isoformat(),
        "callbacks_processed": callbacks_processed,
        "last_callback": last_callback,
        "errors": errors,
    }
    write_listener_reports(payload, reports_path=reports_path)
    return payload


def write_listener_reports(payload: dict[str, Any], *, reports_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "telegram_listener.json"
    md_path = reports_path / "telegram_listener.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# QIC Telegram Listener", ""]
    for key in ("running", "last_update", "callbacks_processed"):
        lines.append(f"- {key}: {payload.get(key)}")
    lines.append(f"- errors: {', '.join(payload.get('errors') or []) or 'none'}")
    lines.append("")
    lines.append("## Last Callback")
    lines.append(json.dumps(payload.get("last_callback"), indent=2, sort_keys=True))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
