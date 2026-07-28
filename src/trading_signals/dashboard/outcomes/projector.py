from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from trading_signals.dashboard.contracts import (
    CollisionPolicy,
    EntryActivationPolicy,
    OutcomeEvaluationPolicy,
    SignalOutcome,
)
from trading_signals.dashboard.ingestion.sanitize import safe_text
from trading_signals.dashboard.metrics.engine import (
    MetricObservation,
    classify_eligibility,
)
from trading_signals.dashboard.outcomes.engine import OutcomeSignal, evaluate_signal_outcome
from trading_signals.dashboard.outcomes.sources import (
    RiskPlanCatalog,
    load_market_snapshots,
    load_risk_plans,
)
from trading_signals.dashboard.storage import (
    connect_read_only,
    connect_writer,
    finalize_writer,
    schema_is_current,
    validate_read_model_path,
)

DEFAULT_OUTCOME_POLICY_VERSION = "closed-bars-entry-touch-v1"


@dataclass(frozen=True, slots=True)
class OutcomeProjectionConfig:
    data_root: Path
    sqlite_path: Path
    risk_plans_root: Path
    market_snapshots_root: Path
    policy: OutcomeEvaluationPolicy
    as_of: datetime


@dataclass(frozen=True, slots=True)
class OutcomeProjectionSummary:
    policy_version: str
    engine_version: str
    signals_seen: int
    signals_evaluated: int
    missing_levels: int
    inserted: int
    already_present: int
    status_counts: Mapping[str, int]
    market_records_seen: int
    completed_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_outcome_policy(
    *,
    timeframe: str = "1h",
    horizon_candles: int = 24,
    policy_version: str = DEFAULT_OUTCOME_POLICY_VERSION,
    collision_policy: CollisionPolicy = CollisionPolicy.AMBIGUOUS,
) -> OutcomeEvaluationPolicy:
    return OutcomeEvaluationPolicy(
        policy_version=policy_version,
        timeframe=timeframe,
        horizon_candles=horizon_candles,
        entry_activation_policy=EntryActivationPolicy.REQUIRE_POST_DECISION_TOUCH,
        collision_policy=collision_policy,
        require_contiguous_candles=True,
        closed_candles_only=True,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("as-of timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _policy_payload(policy: OutcomeEvaluationPolicy) -> str:
    return json.dumps(
        policy.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def _register_policy(connection: sqlite3.Connection, policy: OutcomeEvaluationPolicy) -> None:
    payload = _policy_payload(policy)
    existing = connection.execute(
        "SELECT policy_json FROM outcome_policies WHERE policy_version=?",
        (policy.policy_version,),
    ).fetchone()
    if existing is not None and str(existing[0]) != payload:
        raise RuntimeError("outcome policy version already exists with different semantics")
    connection.execute(
        """
        INSERT OR IGNORE INTO outcome_policies(
            policy_version, engine_version, timeframe, horizon_candles,
            entry_activation_policy, collision_policy,
            require_contiguous_candles, closed_candles_only,
            policy_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy.policy_version,
            policy.engine_version,
            policy.timeframe,
            policy.horizon_candles,
            policy.entry_activation_policy.value,
            policy.collision_policy.value,
            int(policy.require_contiguous_candles),
            int(policy.closed_candles_only),
            payload,
            datetime.now(tz=UTC).isoformat(),
        ),
    )


def _raw_payload(row: sqlite3.Row) -> dict[str, object]:
    try:
        parsed = json.loads(str(row["raw_payload_json"]))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _outcome_signal(
    row: sqlite3.Row,
    risk_plans: RiskPlanCatalog,
) -> tuple[OutcomeSignal, bool]:
    raw = _raw_payload(row)
    risk_plan_id = safe_text(raw.get("risk_plan_id"))
    risk = risk_plans.records.get(risk_plan_id or "")
    timestamp = datetime.fromisoformat(str(row["event_timestamp"]).replace("Z", "+00:00"))
    missing_levels = risk is None
    return (
        OutcomeSignal(
            projection_key=str(row["projection_key"]),
            signal_id=safe_text(row["signal_id"]),
            symbol=str(row["symbol"] or ""),
            direction=str(row["decision"] or row["direction"] or ""),
            timeframe=str(row["timeframe"] or ""),
            decision_at=timestamp,
            entry_price=risk.entry if risk else None,
            stop_price=risk.stop_loss if risk else None,
            target_price=risk.take_profit if risk else None,
            strategy_version=safe_text(row["strategy_version"]),
            signal_policy_version=safe_text(row["policy_version"]),
        ),
        missing_levels,
    )


def _outcome_id(outcome: SignalOutcome) -> str:
    material = "|".join(
        (
            outcome.identity.projection_key,
            outcome.policy_version,
            outcome.market_source.source_fingerprint,
        )
    )
    return hashlib.sha256(f"signal_outcome:{material}".encode("utf-8")).hexdigest()


def _entry_enrichment(
    outcome: SignalOutcome,
    outcome_id: str,
) -> dict[str, object]:
    activation = next(
        (item for item in outcome.evidence if item.entry_touched),
        None,
    )
    activated = activation is not None
    evidence_id = (
        hashlib.sha256(
            f"{outcome_id}|{activation.candle_index}|{activation.open_at.isoformat()}".encode(
                "utf-8"
            )
        ).hexdigest()
        if activation
        else None
    )
    exact_activation_at = (
        activation.open_at
        if activation is not None
        and outcome.entry_price is not None
        and activation.open_price == outcome.entry_price
        else None
    )
    observation = MetricObservation(
        outcome_id=outcome_id,
        signal_projection_key=outcome.identity.projection_key,
        symbol=outcome.identity.symbol,
        direction=outcome.direction,
        timeframe=outcome.timeframe,
        setup=None,
        strategy_version=outcome.identity.strategy_version,
        policy_version=outcome.policy_version,
        engine_version=outcome.engine_version,
        market_data_fingerprint=outcome.market_source.source_fingerprint,
        data_quality=outcome.data_quality.value,
        terminal_status=outcome.terminal_status.value,
        entry_timestamp=outcome.entry_timestamp,
        entry_price=outcome.entry_price,
        stop_price=outcome.stop_price,
        target_price=outcome.target_price,
        entry_activated=activated,
        entry_activated_at=exact_activation_at,
        entry_activation_candle_open=activation.open_at if activation else None,
        candles_until_entry=activation.candle_index if activation else None,
        candles_after_entry=(
            outcome.candles_observed - activation.candle_index
            if activation
            else None
        ),
        ambiguity_reason=outcome.ambiguity_reason,
    )
    decision = classify_eligibility(observation)
    return {
        "entry_activated": int(activated),
        "entry_activated_at": (
            exact_activation_at.isoformat() if exact_activation_at else None
        ),
        "entry_activation_candle_open": (
            activation.open_at.isoformat() if activation else None
        ),
        "entry_activation_evidence_id": evidence_id,
        "candles_until_entry": activation.candle_index if activation else None,
        "candles_after_entry": (
            outcome.candles_observed - activation.candle_index
            if activation
            else None
        ),
        "entry_lifecycle_status": decision.lifecycle.value,
        "eligibility_status": decision.status.value,
        "eligibility_reason": decision.reason_code,
    }


def _persist_outcome(
    connection: sqlite3.Connection,
    outcome: SignalOutcome,
    row: sqlite3.Row,
) -> bool:
    source = outcome.market_source
    source_payload = json.dumps(
        {
            "logical_source_name": source.logical_source_name,
            "timeframe": source.timeframe,
            "candles_count": source.candles_count,
            "data_quality": source.data_quality.value,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO market_data_sources(
            market_data_fingerprint, logical_source_name, source_format,
            timeframe, coverage_start, coverage_end, candles_count,
            data_quality, source_reference, payload_json, registered_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source.source_fingerprint,
            source.logical_source_name,
            source.source_format,
            source.timeframe,
            source.coverage_start.isoformat() if source.coverage_start else None,
            source.coverage_end.isoformat() if source.coverage_end else None,
            source.candles_count,
            source.data_quality.value,
            source.source_reference,
            source_payload,
            outcome.computed_at.isoformat(),
        ),
    )
    outcome_id = _outcome_id(outcome)
    entry = _entry_enrichment(outcome, outcome_id)
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO signal_outcomes(
            outcome_id, signal_projection_key, signal_id, symbol, direction,
            timeframe, entry_timestamp, evaluation_start, evaluation_end,
            entry_price, stop_price, target_price, candles_expected,
            candles_observed, first_stop_touch_at, first_target_touch_at,
            terminal_status, terminal_timestamp, terminal_price,
            ambiguity_reason, data_quality, policy_version, engine_version,
            market_data_fingerprint, source_fingerprint, git_commit_sha,
            deployment_id, config_hash, selected_engine, strategy_version,
            signal_policy_version, experiment_id, computed_at,
            entry_activated, entry_activated_at,
            entry_activation_candle_open, entry_activation_evidence_id,
            candles_until_entry, candles_after_entry, entry_lifecycle_status,
            eligibility_status, eligibility_reason
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            outcome_id,
            outcome.identity.projection_key,
            outcome.identity.signal_id,
            outcome.identity.symbol,
            outcome.direction,
            outcome.timeframe,
            outcome.entry_timestamp.isoformat(),
            outcome.evaluation_start.isoformat() if outcome.evaluation_start else None,
            outcome.evaluation_end.isoformat() if outcome.evaluation_end else None,
            outcome.entry_price,
            outcome.stop_price,
            outcome.target_price,
            outcome.candles_expected,
            outcome.candles_observed,
            outcome.first_stop_touch.isoformat() if outcome.first_stop_touch else None,
            outcome.first_target_touch.isoformat() if outcome.first_target_touch else None,
            outcome.terminal_status.value,
            outcome.terminal_timestamp.isoformat() if outcome.terminal_timestamp else None,
            outcome.terminal_price,
            outcome.ambiguity_reason,
            outcome.data_quality.value,
            outcome.policy_version,
            outcome.engine_version,
            source.source_fingerprint,
            outcome.source_fingerprint,
            safe_text(row["git_commit_sha"]),
            safe_text(row["deployment_id"]),
            safe_text(row["config_hash"]),
            safe_text(row["selected_engine"]),
            safe_text(row["strategy_version"]),
            safe_text(row["policy_version"]),
            safe_text(row["experiment_id"]),
            outcome.computed_at.isoformat(),
            entry["entry_activated"],
            entry["entry_activated_at"],
            entry["entry_activation_candle_open"],
            entry["entry_activation_evidence_id"],
            entry["candles_until_entry"],
            entry["candles_after_entry"],
            entry["entry_lifecycle_status"],
            entry["eligibility_status"],
            entry["eligibility_reason"],
        ),
    )
    if cursor.rowcount != 1:
        return False
    for item in outcome.evidence:
        evidence_id = hashlib.sha256(
            f"{outcome_id}|{item.candle_index}|{item.open_at.isoformat()}".encode("utf-8")
        ).hexdigest()
        evidence_json = json.dumps(
            {
                "entry_touched": item.entry_touched,
                "stop_touched": item.stop_touched,
                "target_touched": item.target_touched,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        connection.execute(
            """
            INSERT INTO outcome_evidence(
                evidence_id, outcome_id, candle_index, candle_open_at,
                candle_close_at, open_price, high_price, low_price,
                close_price, entry_touched, stop_touched, target_touched,
                evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                outcome_id,
                item.candle_index,
                item.open_at.isoformat(),
                item.close_at.isoformat(),
                item.open_price,
                item.high_price,
                item.low_price,
                item.close_price,
                int(item.entry_touched),
                int(item.stop_touched),
                int(item.target_touched),
                evidence_json,
            ),
        )
    return True


def project_outcomes_once(config: OutcomeProjectionConfig) -> OutcomeProjectionSummary:
    database = validate_read_model_path(config.sqlite_path, data_root=config.data_root)
    if not database.is_file():
        raise RuntimeError("read model does not exist")
    as_of = _utc(config.as_of)
    risk_plans = load_risk_plans(config.risk_plans_root, data_root=config.data_root)
    market = load_market_snapshots(
        config.market_snapshots_root,
        data_root=config.data_root,
    )
    connection = connect_writer(database, data_root=config.data_root)
    signals_seen = evaluated = missing_levels = inserted = already_present = 0
    status_counts: dict[str, int] = {}
    try:
        if not schema_is_current(connection):
            raise RuntimeError("read model is not migrated")
        rows = tuple(
            connection.execute(
                """
                SELECT * FROM signals
                WHERE lower(COALESCE(decision, direction, '')) IN ('long', 'short')
                  AND timeframe=?
                ORDER BY event_timestamp, projection_key
                """,
                (config.policy.timeframe,),
            )
        )
        connection.execute("BEGIN IMMEDIATE")
        _register_policy(connection, config.policy)
        for row in rows:
            signals_seen += 1
            signal, levels_missing = _outcome_signal(row, risk_plans)
            missing_levels += int(levels_missing)
            outcome = evaluate_signal_outcome(
                signal,
                market.series(signal.symbol, signal.timeframe),
                policy=config.policy,
                as_of=as_of,
                source_name="market_snapshots",
                source_format="json_files",
            )
            evaluated += 1
            status_counts[outcome.terminal_status.value] = (
                status_counts.get(outcome.terminal_status.value, 0) + 1
            )
            if _persist_outcome(connection, outcome, row):
                inserted += 1
            else:
                already_present += 1
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        try:
            finalize_writer(connection)
        finally:
            connection.close()
    return OutcomeProjectionSummary(
        policy_version=config.policy.policy_version,
        engine_version=config.policy.engine_version,
        signals_seen=signals_seen,
        signals_evaluated=evaluated,
        missing_levels=missing_levels,
        inserted=inserted,
        already_present=already_present,
        status_counts=dict(sorted(status_counts.items())),
        market_records_seen=market.records_seen,
        completed_at=datetime.now(tz=UTC).isoformat(),
    )


def inspect_outcome(sqlite_path: Path, signal_key: str) -> dict[str, object]:
    if not signal_key or len(signal_key) > 128:
        raise ValueError("signal key is invalid")
    connection = connect_read_only(sqlite_path)
    try:
        if not schema_is_current(connection):
            return {"status": "schema_unavailable", "outcomes": ()}
        rows = tuple(
            connection.execute(
                """
                SELECT outcome_id, signal_id, symbol, direction, timeframe,
                       entry_timestamp, evaluation_start, evaluation_end,
                       candles_expected, candles_observed, terminal_status,
                       terminal_timestamp, ambiguity_reason, data_quality,
                       policy_version, engine_version, market_data_fingerprint,
                       computed_at
                FROM signal_outcomes
                WHERE signal_projection_key=? OR signal_id=?
                ORDER BY computed_at DESC
                """,
                (signal_key, signal_key),
            )
        )
        return {
            "status": "ok" if rows else "not_found",
            "outcomes": tuple(dict(row) for row in rows),
        }
    finally:
        connection.close()
