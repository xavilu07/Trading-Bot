from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

from trading_signals.dashboard.ingestion.paper_trace import project_paper_trace
from trading_signals.paper_trace.contracts import ProspectiveSignalIdentity, TargetRole, TraceCandle
from trading_signals.paper_trace.engine import advance_trace, start_trace
from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
    TRACE_MODEL_VERSION,
    trace_policy_checksum,
    trace_policy_specification,
)
from trading_signals.paper_trace.sanitize import stable_hash
from trading_signals.paper_trace.state_machine import replay_receipts
from trading_signals.paper_trace.store import JsonlTraceStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-trace")
    parser.add_argument(
        "operation",
        choices=(
            "trace-validate",
            "trace-inspect",
            "trace-replay",
            "trace-project",
            "trace-policy",
            "trace-store-health",
            "trace-simulate",
        ),
    )
    parser.add_argument("--store-path", type=Path)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--allowed-root", type=Path)
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--sqlite-path", type=Path)
    parser.add_argument("--trace-id")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _store(arguments: argparse.Namespace) -> JsonlTraceStore:
    if arguments.store_path is None or arguments.data_root is None:
        raise ValueError("TRACE_STORE_AND_DATA_ROOT_REQUIRED")
    return JsonlTraceStore(
        arguments.store_path.expanduser(),
        data_root=arguments.data_root.expanduser(),
        allowed_root=(
            arguments.allowed_root.expanduser()
            if arguments.allowed_root is not None
            else None
        ),
        max_bytes=arguments.max_bytes,
    )


def _safe_receipt(receipt: object) -> dict[str, object]:
    values = receipt.to_dict()
    return {
        key: values[key]
        for key in (
            "receipt_id",
            "trace_id",
            "event_type",
            "event_sequence",
            "occurred_at",
            "signal_id",
            "order_id",
            "fill_id",
            "position_id",
            "candle_open_time",
            "symbol",
            "timeframe",
            "reason_code",
            "policy_id",
            "policy_version",
            "model_version",
            "receipt_hash",
        )
    }


def _synthetic_identity() -> ProspectiveSignalIdentity:
    at = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    fingerprint = stable_hash({"fixture": "synthetic"}, namespace="paper_trace_fixture.v1")
    return ProspectiveSignalIdentity(
        signal_id="synthetic-signal-001",
        signal_schema_version="paper.signal.identity.v1",
        created_at=at,
        decision_at=at,
        symbol="SYNTHETICUSDT",
        direction="long",
        timeframe="1h",
        strategy_id="synthetic-strategy",
        strategy_version="v1",
        strategy_commit="0" * 40,
        setup_id="synthetic-setup",
        setup_version="v1",
        setup_parameters_hash=fingerprint,
        policy_id="public-safety-policy",
        policy_version="v1",
        fill_policy_id=DEFAULT_FILL_POLICY_ID,
        fill_policy_version=trace_policy_checksum(),
        expiry_policy_id=DEFAULT_EXPIRY_POLICY_ID,
        engine_version=TRACE_MODEL_VERSION,
        config_hash=fingerprint,
        market_context_fingerprint=fingerprint,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        target_role=TargetRole.FINAL_TARGET,
        target_index=2,
        horizon_candles=24,
        source_cycle_id="synthetic-cycle-001",
        source_agent_decision_id=None,
        correlation_group_id=None,
    )


def _simulate(store: JsonlTraceStore | None, *, dry_run: bool) -> dict[str, object]:
    identity = _synthetic_identity()
    start = start_trace(identity, accepted=True, observed_at=identity.decision_at)
    receipts = list(start.receipts)
    entry = TraceCandle(
        symbol=identity.symbol,
        timeframe="1h",
        open_at=identity.decision_at,
        close_at=identity.decision_at + timedelta(hours=1),
        open_price=99.0,
        high_price=101.0,
        low_price=98.0,
        close_price=100.5,
    )
    first = advance_trace(
        identity,
        receipts,
        entry,
        observed_at=entry.close_at,
    )
    receipts.extend(first.receipts)
    target = TraceCandle(
        symbol=identity.symbol,
        timeframe="1h",
        open_at=entry.close_at,
        close_at=entry.close_at + timedelta(hours=1),
        open_price=101.0,
        high_price=111.0,
        low_price=100.0,
        close_price=110.0,
    )
    second = advance_trace(
        identity,
        receipts,
        target,
        observed_at=target.close_at,
    )
    receipts.extend(second.receipts)
    if not dry_run:
        if store is None:
            raise ValueError("TRACE_STORE_REQUIRED")
        store.append(receipts)
    state = replay_receipts(receipts)
    return {
        "dry_run": dry_run,
        "receipt_count": len(receipts),
        "trace_id": start.trace_id,
        "state": {
            "signal": state.signal.value,
            "order": state.order.value,
            "position": state.position.value,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.operation == "trace-policy":
            result: object = {
                "policy": trace_policy_specification(),
                "checksum": trace_policy_checksum(),
            }
        elif arguments.operation == "trace-simulate":
            store = None if arguments.dry_run else _store(arguments)
            result = _simulate(store, dry_run=arguments.dry_run)
        else:
            store = _store(arguments)
            if arguments.operation in {"trace-validate", "trace-store-health"}:
                result = store.health().to_dict()
            elif arguments.operation in {"trace-inspect", "trace-replay"}:
                if not arguments.trace_id:
                    raise ValueError("TRACE_ID_REQUIRED")
                receipts = store.read_trace(arguments.trace_id)
                state = replay_receipts(receipts)
                result = {
                    "trace_id": arguments.trace_id,
                    "state": {
                        "signal": state.signal.value,
                        "order": state.order.value,
                        "position": state.position.value,
                        "last_sequence": state.last_sequence,
                        "trace_blocked_reason": state.trace_blocked_reason,
                    },
                    "receipts": (
                        [_safe_receipt(receipt) for receipt in receipts]
                        if arguments.operation == "trace-inspect"
                        else []
                    ),
                }
            elif arguments.operation == "trace-project":
                if arguments.sqlite_path is None or arguments.data_root is None:
                    raise ValueError("SQLITE_PATH_AND_DATA_ROOT_REQUIRED")
                result = project_paper_trace(
                    source_path=store.path,
                    sqlite_path=arguments.sqlite_path.expanduser(),
                    data_root=arguments.data_root.expanduser(),
                    dry_run=arguments.dry_run,
                ).to_dict()
            else:
                raise ValueError("OPERATION_UNSUPPORTED")
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": str(getattr(exc, "code", "TRACE_COMMAND_FAILED"))[:100],
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps({"status": "ok", "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
