from __future__ import annotations

import argparse
import json
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.qic_telegram_config import load_qic_telegram_config
from trading_signals.agents.qic_runtime import ProcessLock, atomic_write_json, atomic_write_text, read_json_safe
from trading_signals.agents.telegram_approval import poll_approval_callbacks


_STOP_REQUESTED = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run persistent QIC Telegram callback listener.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--reports-path", type=Path, default=Path("reports") / "qic")
    parser.add_argument("--lock-path", type=Path, default=Path("data") / "qic" / "locks" / "telegram_listener.lock")
    parser.add_argument("--offset-path", type=Path, default=Path("data") / "qic" / "telegram_update_offset.json")
    parser.add_argument("--callback-history-path", type=Path, default=Path("data") / "qic" / "telegram_callbacks.jsonl")
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

    previous = read_json_safe(args.reports_path / "telegram_listener.json", {})
    total_processed = int(previous.get("callbacks_processed") or 0) if isinstance(previous, dict) else 0
    errors: list[str] = list(previous.get("errors") or []) if isinstance(previous, dict) else []
    last_callback = previous.get("last_callback") if isinstance(previous, dict) else None
    lock = ProcessLock(args.lock_path, stale_after_seconds=180)
    if not lock.acquire():
        report = _listener_report(
            running=False,
            callbacks_processed=total_processed,
            last_callback=last_callback,
            errors=[*errors[-19:], "telegram_listener_lock_already_held"],
            reports_path=args.reports_path,
            status="blocked_duplicate_listener",
            config_source=str(config.get("source")),
            authorized_chat_count=len(config.get("chat_ids") or []),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    _install_signal_handlers()
    consecutive_failures = 0
    try:
        while not _STOP_REQUESTED:
            result = poll_approval_callbacks(
                bot_token=str(config["bot_token"]),
                limit=args.limit,
                timeout=args.timeout,
                dry_run=args.dry_run,
                authorized_chat_ids=list(config.get("chat_ids") or []),
                offset_path=args.offset_path,
                callback_history_path=args.callback_history_path,
            )
            processed = result.get("processed") if isinstance(result.get("processed"), list) else []
            total_processed += len(processed)
            if processed:
                last_callback = processed[-1]
            if result.get("status") not in {"ok", "dry_run"}:
                consecutive_failures += 1
                errors.append(str(result.get("error_message") or result.get("reason") or result.get("status")))
            else:
                consecutive_failures = 0
            report = _listener_report(
                running=not args.once and not _STOP_REQUESTED,
                callbacks_processed=total_processed,
                last_callback=last_callback,
                errors=errors[-20:],
                reports_path=args.reports_path,
                status="running" if not args.once else str(result.get("status")),
                config_source=str(config.get("source")),
                authorized_chat_count=len(config.get("chat_ids") or []),
                update_offset=result.get("next_offset"),
                consecutive_failures=consecutive_failures,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if args.once:
                return 0 if result.get("status") in {"ok", "dry_run"} else 1
            backoff = min(60.0, max(args.poll_interval, 1.0) * (2 ** min(consecutive_failures, 5)))
            time.sleep(backoff)
    finally:
        lock.release()
        if not args.once:
            _listener_report(
                running=False,
                callbacks_processed=total_processed,
                last_callback=last_callback,
                errors=errors[-20:],
                reports_path=args.reports_path,
                status="stopped",
                config_source=str(config.get("source")),
                authorized_chat_count=len(config.get("chat_ids") or []),
            )
    return 0


def _listener_report(
    *,
    running: bool,
    callbacks_processed: int,
    last_callback: dict[str, Any] | None,
    errors: list[str],
    reports_path: Path,
    status: str = "running",
    config_source: str = "",
    authorized_chat_count: int = 0,
    update_offset: Any = None,
    consecutive_failures: int = 0,
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "status": status,
        "running": running,
        "last_update": datetime.now(tz=UTC).isoformat(),
        "callbacks_processed": callbacks_processed,
        "last_callback": last_callback,
        "errors": errors,
        "config_source": config_source,
        "authorized_chat_count": authorized_chat_count,
        "update_offset": update_offset,
        "consecutive_failures": consecutive_failures,
    }
    write_listener_reports(payload, reports_path=reports_path)
    return payload


def write_listener_reports(payload: dict[str, Any], *, reports_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "telegram_listener.json"
    md_path = reports_path / "telegram_listener.md"
    atomic_write_json(json_path, payload)
    atomic_write_text(md_path, _markdown(payload))
    return {"json": json_path, "markdown": md_path}


def _markdown(payload: dict[str, Any]) -> str:
    lines = ["# QIC Telegram Listener", ""]
    for key in ("status", "running", "last_update", "callbacks_processed", "authorized_chat_count", "update_offset", "consecutive_failures"):
        lines.append(f"- {key}: {payload.get(key)}")
    lines.append(f"- errors: {', '.join(payload.get('errors') or []) or 'none'}")
    lines.append("")
    lines.append("## Last Callback")
    lines.append(json.dumps(payload.get("last_callback"), indent=2, sort_keys=True))
    return "\n".join(lines) + "\n"


def _install_signal_handlers() -> None:
    def request_stop(signum: int, frame: Any) -> None:
        del signum, frame
        global _STOP_REQUESTED
        _STOP_REQUESTED = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)


if __name__ == "__main__":
    raise SystemExit(main())
