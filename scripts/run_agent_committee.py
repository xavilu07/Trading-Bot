from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from trading_signals.agents.committee import run_agent_committee
from trading_signals.app.settings import load_settings


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Agent Committee V1 offline.")
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--data-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=Path("reports") / "qic")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--min-confidence", choices=["LOW", "MEDIUM", "HIGH"], default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run even if AGENT_COMMITTEE_ENABLED=false.")
    parser.add_argument("--legacy-v1", action="store_true", help="Use the old independent-proposals committee flow.")
    args = parser.parse_args(argv)

    load_dotenv(args.env_file)
    settings = load_settings()
    try:
        result = run_agent_committee(
            reports_root=args.reports_root,
            data_path=args.data_path or _setting(settings, "data_storage_path", Path("data")),
            output_path=args.output_path,
            enabled=_bool_setting(settings, "agent_committee_enabled", False),
            min_confidence=args.min_confidence or str(_setting(settings, "agent_committee_min_confidence", "MEDIUM")),
            telegram_enabled=_bool_setting(settings, "qic_telegram_enabled", _bool_setting(settings, "agent_telegram_approval_enabled", False)),
            telegram_bot_token=str(
                _setting(settings, "qic_telegram_bot_token", "")
                or _setting(settings, "agent_telegram_bot_token", "")
                or _setting(settings, "telegram_bot_token", "")
            ),
            telegram_chat_id=str(
                _setting(settings, "qic_telegram_chat_id", "")
                or _setting(settings, "agent_telegram_chat_id", "")
                or _setting(settings, "telegram_dev_chat_id", "")
            ),
            telegram_send_no_actionable=_bool_setting(settings, "qic_telegram_send_no_actionable", True),
            telegram_min_priority=str(_setting(settings, "qic_telegram_min_priority", "MEDIUM")),
            dry_run=args.dry_run,
            force=args.force,
            use_qic_v2=not args.legacy_v1,
        )
    except Exception as exc:
        _write_failure_reports(args.output_path, exc)
        print(
            json.dumps(
                {
                    "enabled": False,
                    "proposal_count": 0,
                    "proposal_store": None,
                    "telegram_results": [],
                    "reports_path": str(args.output_path),
                    "status": "failed",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(
        {
            "enabled": result.get("enabled"),
            "proposal_count": result.get("proposal_count", 0),
            "proposal_store": result.get("proposal_store"),
            "telegram_results": result.get("telegram_results", []),
            "reports_path": str(args.output_path),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def _setting(settings: object, name: str, default: Any) -> Any:
    return getattr(settings, name, default)


def _bool_setting(settings: object, name: str, default: bool) -> bool:
    value = _setting(settings, name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _write_failure_reports(output_path: Path, exc: Exception) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "failed",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "proposal_count": 0,
        "single_proposal": None,
    }
    for name in ("debate", "consensus", "proposal", "agent_memory"):
        json_path = output_path / f"{name}.json"
        md_path = output_path / f"{name}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(
            f"# QIC {name.replace('_', ' ').title()}\n\nStatus: failed\n\nError: {type(exc).__name__}: {exc}\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
