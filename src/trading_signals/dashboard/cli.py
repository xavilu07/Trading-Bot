from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from trading_signals.dashboard.contracts import CollisionPolicy
from trading_signals.dashboard.ingestion.projector import (
    PROJECTED_SOURCES,
    ProjectorConfig,
    inspect_read_model,
    migrate_read_model,
    project_once,
    rebuild_read_model,
)
from trading_signals.dashboard.outcomes.projector import (
    OutcomeProjectionConfig,
    default_outcome_policy,
    inspect_outcome,
    project_outcomes_once,
)
from trading_signals.interfaces.dashboard_api.settings import DashboardSettings


def _default_manifest() -> Path:
    return Path(__file__).resolve().parent / "ingestion" / "sources.v1.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantum-dashboard-read-model",
        description="Finite, manual projector for the rebuildable dashboard SQLite read model.",
    )
    parser.add_argument(
        "operation",
        choices=(
            "migrate",
            "project-once",
            "rebuild",
            "inspect",
            "outcomes-once",
            "inspect-outcome",
        ),
    )
    parser.add_argument("--sqlite-path", type=Path)
    parser.add_argument("--manifest-path", type=Path, default=_default_manifest())
    parser.add_argument("--bot-root", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--reports-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--active-signal-log", type=Path)
    parser.add_argument("--scheduler-lock", type=Path)
    parser.add_argument("--risk-plans-root", type=Path)
    parser.add_argument("--market-snapshots-root", type=Path)
    parser.add_argument("--policy-version", default="closed-bars-entry-touch-v1")
    parser.add_argument("--outcome-timeframe", default="1h")
    parser.add_argument("--horizon-candles", type=int, default=24)
    parser.add_argument(
        "--collision-policy",
        choices=tuple(item.value for item in CollisionPolicy),
        default=CollisionPolicy.AMBIGUOUS.value,
    )
    parser.add_argument("--as-of")
    parser.add_argument("--signal-key")
    parser.add_argument(
        "--sources",
        default=",".join(PROJECTED_SOURCES),
        help="Comma-separated allowlist; implemented: scheduler_heartbeat,scan_runs,trade_signals.",
    )
    return parser


def _config(arguments: argparse.Namespace) -> ProjectorConfig:
    defaults = DashboardSettings.from_env()
    bot_root = (arguments.bot_root or defaults.bot_root).expanduser().resolve(strict=False)
    data_root = (arguments.data_root or defaults.data_root).expanduser().resolve(strict=False)
    reports_root = (arguments.reports_root or defaults.reports_root).expanduser().resolve(strict=False)
    runtime_root = (arguments.runtime_root or defaults.runtime_root).expanduser().resolve(strict=False)
    sqlite_path = (
        arguments.sqlite_path or defaults.resolved_read_model_path()
    ).expanduser().resolve(strict=False)
    selected_sources = tuple(item.strip() for item in arguments.sources.split(",") if item.strip())
    unknown = set(selected_sources) - set(PROJECTED_SOURCES)
    if unknown:
        raise ValueError("requested source is not implemented in this projector phase")
    variables: dict[str, Path | None] = {
        "bot_root": bot_root,
        "data_root": data_root,
        "reports_root": reports_root,
        "runtime_root": runtime_root,
        "active_signal_log": (
            arguments.active_signal_log.expanduser().resolve(strict=False)
            if arguments.active_signal_log
            else defaults.active_signal_log
        ),
        "scheduler_lock": (
            arguments.scheduler_lock.expanduser().resolve(strict=False)
            if arguments.scheduler_lock
            else defaults.scheduler_lock
        ),
    }
    return ProjectorConfig(
        data_root=data_root,
        sqlite_path=sqlite_path,
        manifest_path=arguments.manifest_path.expanduser().resolve(strict=True),
        variables=variables,
        selected_sources=selected_sources,
    )


def _parse_as_of(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as-of timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def _outcome_config(
    arguments: argparse.Namespace,
    projector: ProjectorConfig,
) -> OutcomeProjectionConfig:
    return OutcomeProjectionConfig(
        data_root=projector.data_root,
        sqlite_path=projector.sqlite_path,
        risk_plans_root=(
            arguments.risk_plans_root or projector.data_root / "risk_plans"
        ).expanduser().resolve(strict=False),
        market_snapshots_root=(
            arguments.market_snapshots_root or projector.data_root / "market_snapshots"
        ).expanduser().resolve(strict=False),
        policy=default_outcome_policy(
            timeframe=arguments.outcome_timeframe,
            horizon_candles=arguments.horizon_candles,
            policy_version=arguments.policy_version,
            collision_policy=CollisionPolicy(arguments.collision_policy),
        ),
        as_of=_parse_as_of(arguments.as_of),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        config = _config(arguments)
        if arguments.operation == "migrate":
            result: object = {"operation": "migrate", "applied_versions": migrate_read_model(config)}
        elif arguments.operation == "project-once":
            result = {"operation": "project-once", "summary": project_once(config).to_dict()}
        elif arguments.operation == "rebuild":
            result = {"operation": "rebuild", "summary": rebuild_read_model(config).to_dict()}
        elif arguments.operation == "inspect":
            result = {"operation": "inspect", **inspect_read_model(config.sqlite_path)}
        elif arguments.operation == "outcomes-once":
            result = {
                "operation": "outcomes-once",
                "summary": project_outcomes_once(
                    _outcome_config(arguments, config)
                ).to_dict(),
            }
        else:
            if arguments.signal_key is None:
                raise ValueError("inspect-outcome requires --signal-key")
            result = {
                "operation": "inspect-outcome",
                **inspect_outcome(config.sqlite_path, arguments.signal_key),
            }
    except (OSError, RuntimeError, ValueError) as exc:
        code = getattr(exc, "code", "READ_MODEL_COMMAND_FAILED")
        print(json.dumps({"status": "error", "code": str(code)[:80]}, sort_keys=True))
        return 2
    print(json.dumps({"status": "ok", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
