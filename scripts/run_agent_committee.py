from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Agent Committee V1 offline.")
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--data-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=Path("reports") / "agent_committee")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--min-confidence", choices=["LOW", "MEDIUM", "HIGH"], default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run even if AGENT_COMMITTEE_ENABLED=false.")
    args = parser.parse_args()

    load_dotenv(args.env_file)
    settings = load_settings()
    result = run_agent_committee(
        reports_root=args.reports_root,
        data_path=args.data_path or settings.data_storage_path,
        output_path=args.output_path,
        enabled=settings.agent_committee_enabled,
        min_confidence=args.min_confidence or settings.agent_committee_min_confidence,
        telegram_enabled=settings.agent_telegram_approval_enabled,
        telegram_bot_token=settings.agent_telegram_bot_token or settings.telegram_bot_token,
        telegram_chat_id=settings.agent_telegram_chat_id or settings.telegram_dev_chat_id,
        dry_run=args.dry_run,
        force=args.force,
    )
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


if __name__ == "__main__":
    raise SystemExit(main())
