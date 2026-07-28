from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from trading_signals.dashboard.contracts.metrics import EligibilityStatus
from trading_signals.dashboard.metrics.engine import (
    ComputedMetric,
    MetricObservation,
    activated_metrics,
    activation_metrics,
    classify_eligibility,
    gross_plan_r,
    resolved_metrics,
    sample_label,
)
from trading_signals.dashboard.metrics.policy import (
    FROZEN_ENGINE_VERSION,
    FROZEN_POLICY_VERSION,
    METRIC_DEFINITION_VERSION,
    canonical_json,
    frozen_policy_checksum,
    frozen_policy_specification,
)
from trading_signals.dashboard.storage import (
    connect_read_only,
    connect_writer,
    finalize_writer,
    schema_is_current,
    validate_read_model_path,
)

_DIMENSIONS = (
    "strategy_version",
    "policy_version",
    "direction",
    "setup",
    "symbol",
    "timeframe",
    "month_utc",
    "entry_activation",
    "quality",
)
_COMBINED_DIMENSIONS = (
    ("strategy_version", "direction"),
    ("strategy_version", "setup"),
    ("direction", "setup"),
    ("symbol", "direction"),
)


@dataclass(frozen=True, slots=True)
class MetricProjectionConfig:
    data_root: Path
    sqlite_path: Path


@dataclass(frozen=True, slots=True)
class MetricProjectionSummary:
    run_id: str
    policy_version: str
    policy_checksum: str
    engine_version: str
    outcome_dataset_fingerprint: str
    outcomes_observed: int
    signals_observed: int
    entry_activated: int
    eligible_resolved: int
    eligible_activated_expired: int
    excluded: int
    cohorts_written: int
    metric_values_written: int
    already_present: bool
    completed_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _Cohort:
    name: str
    observations: tuple[MetricObservation, ...]
    dimension_name: str | None
    dimension_value: str | None
    metric_kind: str


def _utc_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError("METRIC_TIMESTAMP_NOT_UTC")
    return parsed.astimezone(UTC)


def _optional_utc(value: object) -> datetime | None:
    return _utc_text(value) if value else None


def _load_observations(connection: sqlite3.Connection) -> tuple[MetricObservation, ...]:
    rows = connection.execute(
        """
        SELECT o.*, s.setup
        FROM signal_outcomes o
        JOIN signals s ON s.projection_key=o.signal_projection_key
        ORDER BY o.entry_timestamp, o.outcome_id
        """
    )
    observations: list[MetricObservation] = []
    for row in rows:
        if row["entry_activated"] is None or row["eligibility_status"] is None:
            raise RuntimeError("OUTCOMES_REQUIRE_ENTRY_ENRICHMENT")
        observations.append(
            MetricObservation(
                outcome_id=str(row["outcome_id"]),
                signal_projection_key=str(row["signal_projection_key"]),
                symbol=str(row["symbol"]),
                direction=str(row["direction"]),
                timeframe=str(row["timeframe"]),
                setup=str(row["setup"]) if row["setup"] else None,
                strategy_version=(
                    str(row["strategy_version"]) if row["strategy_version"] else None
                ),
                policy_version=str(row["policy_version"]),
                engine_version=str(row["engine_version"]),
                market_data_fingerprint=str(row["market_data_fingerprint"]),
                data_quality=str(row["data_quality"]),
                terminal_status=str(row["terminal_status"]),
                entry_timestamp=_utc_text(row["entry_timestamp"]),
                entry_price=(
                    float(row["entry_price"]) if row["entry_price"] is not None else None
                ),
                stop_price=(
                    float(row["stop_price"]) if row["stop_price"] is not None else None
                ),
                target_price=(
                    float(row["target_price"]) if row["target_price"] is not None else None
                ),
                entry_activated=bool(row["entry_activated"]),
                entry_activated_at=_optional_utc(row["entry_activated_at"]),
                entry_activation_candle_open=_optional_utc(
                    row["entry_activation_candle_open"]
                ),
                candles_until_entry=(
                    int(row["candles_until_entry"])
                    if row["candles_until_entry"] is not None
                    else None
                ),
                candles_after_entry=(
                    int(row["candles_after_entry"])
                    if row["candles_after_entry"] is not None
                    else None
                ),
                ambiguity_reason=(
                    str(row["ambiguity_reason"]) if row["ambiguity_reason"] else None
                ),
            )
        )
    return tuple(observations)


def _verify_frozen_policy(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        """
        SELECT * FROM outcome_policies WHERE policy_version=?
        """,
        (FROZEN_POLICY_VERSION,),
    ).fetchone()
    if row is None:
        raise RuntimeError("FROZEN_OUTCOME_POLICY_MISSING")
    expected = {
        "engine_version": FROZEN_ENGINE_VERSION,
        "timeframe": "1h",
        "horizon_candles": 24,
        "entry_activation_policy": "REQUIRE_POST_DECISION_TOUCH",
        "collision_policy": "AMBIGUOUS",
        "require_contiguous_candles": 1,
        "closed_candles_only": 1,
    }
    if any(row[key] != value for key, value in expected.items()):
        raise RuntimeError("FROZEN_OUTCOME_POLICY_MISMATCH")
    frozen_policy_specification()


def _dataset_fingerprint(observations: Sequence[MetricObservation]) -> str:
    payload = [
        {
            "outcome_id": item.outcome_id,
            "signal": item.signal_projection_key,
            "status": item.terminal_status,
            "quality": item.data_quality,
            "market": item.market_data_fingerprint,
            "policy": item.policy_version,
            "engine": item.engine_version,
            "entry_activated": item.entry_activated,
            "entry_candle": (
                item.entry_activation_candle_open.isoformat()
                if item.entry_activation_candle_open
                else None
            ),
            "levels": [item.entry_price, item.stop_price, item.target_price],
        }
        for item in observations
    ]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _cohort_fingerprint(
    name: str,
    observations: Sequence[MetricObservation],
    dimension_name: str | None,
    dimension_value: str | None,
) -> str:
    payload = {
        "name": name,
        "dimension_name": dimension_name,
        "dimension_value": dimension_value,
        "outcomes": sorted(item.outcome_id for item in observations),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _dimension_value(observation: MetricObservation, dimension: str) -> str:
    if dimension == "month_utc":
        return observation.entry_timestamp.strftime("%Y-%m")
    if dimension == "entry_activation":
        return "ENTRY_ACTIVATED" if observation.entry_activated else "ENTRY_NOT_ACTIVATED"
    if dimension == "quality":
        return observation.data_quality
    value = getattr(observation, dimension)
    return str(value) if value not in (None, "") else "NO_EVIDENCE"


def _cohorts(observations: Sequence[MetricObservation]) -> tuple[_Cohort, ...]:
    resolved = tuple(
        item
        for item in observations
        if classify_eligibility(item).status is EligibilityStatus.ELIGIBLE_RESOLVED
    )
    activated = tuple(
        item
        for item in observations
        if classify_eligibility(item).status
        in {EligibilityStatus.ELIGIBLE_RESOLVED, EligibilityStatus.ELIGIBLE_ACTIVATED}
    )
    output = [
        _Cohort("ALL_EVALUATED", tuple(observations), None, None, "activation"),
        _Cohort("ELIGIBLE_RESOLVED", resolved, None, None, "resolved"),
        _Cohort("ELIGIBLE_ACTIVATED", activated, None, None, "activated"),
    ]
    for dimension in _DIMENSIONS:
        grouped: dict[str, list[MetricObservation]] = {}
        for item in resolved:
            grouped.setdefault(_dimension_value(item, dimension), []).append(item)
        for value, items in sorted(grouped.items()):
            output.append(
                _Cohort(
                    f"ELIGIBLE_RESOLVED_BY_{dimension.upper()}",
                    tuple(items),
                    dimension,
                    value,
                    "resolved",
                )
            )
    for left, right in _COMBINED_DIMENSIONS:
        grouped_combined: dict[str, list[MetricObservation]] = {}
        for item in resolved:
            left_value = _dimension_value(item, left)
            right_value = _dimension_value(item, right)
            if "NO_EVIDENCE" in {left_value, right_value}:
                continue
            value = f"{left_value}|{right_value}"
            grouped_combined.setdefault(value, []).append(item)
        for value, items in sorted(grouped_combined.items()):
            if len(items) < 20:
                continue
            output.append(
                _Cohort(
                    f"ELIGIBLE_RESOLVED_BY_{left.upper()}_{right.upper()}",
                    tuple(items),
                    f"{left}+{right}",
                    value,
                    "resolved",
                )
            )
    return tuple(output)


def _definition_payload(metric: ComputedMetric, cohort_kind: str) -> dict[str, object]:
    formulas = {
        "resolved_win_rate": "wins/(wins+losses)",
        "resolved_loss_rate": "losses/(wins+losses)",
        "total_gross_plan_r": "sum(gross_plan_r for resolved outcomes)",
        "average_gross_plan_r": "mean(gross_plan_r for resolved outcomes)",
        "median_gross_plan_r": "median(gross_plan_r for resolved outcomes)",
        "gross_plan_expectancy_r": "mean(gross_plan_r for resolved outcomes)",
        "gross_plan_profit_factor": "sum(positive_r)/abs(sum(negative_r))",
        "entry_activation_rate": "entry_activated/directional_signals_evaluated",
        "complete_evidence_coverage": "complete_evidence/directional_signals_evaluated",
        "resolved_outcome_rate_on_activated": "(wins+losses)/(wins+losses+activated_expired)",
    }
    return {
        "name": metric.name,
        "version": METRIC_DEFINITION_VERSION,
        "cohort_kind": cohort_kind,
        "unit": metric.unit,
        "formula": formulas.get(metric.name, metric.name),
        "gross_only": metric.unit == "R",
        "fees_included": False,
        "slippage_included": False,
        "capital_metric": False,
    }


def _register_definition(
    connection: sqlite3.Connection,
    metric: ComputedMetric,
    cohort_kind: str,
    now: str,
) -> str:
    payload = _definition_payload(metric, cohort_kind)
    encoded = canonical_json(payload)
    checksum = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    key = hashlib.sha256(
        f"metric_definition:{METRIC_DEFINITION_VERSION}|{cohort_kind}|{metric.name}".encode(
            "utf-8"
        )
    ).hexdigest()
    existing = connection.execute(
        "SELECT definition_checksum FROM metric_definitions WHERE definition_key=?",
        (key,),
    ).fetchone()
    if existing is not None and str(existing[0]) != checksum:
        raise RuntimeError("METRIC_DEFINITION_CHECKSUM_MISMATCH")
    connection.execute(
        """
        INSERT OR IGNORE INTO metric_definitions(
            definition_key, definition_version, metric_name, cohort_kind,
            unit, formula, definition_json, definition_checksum, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            METRIC_DEFINITION_VERSION,
            metric.name,
            cohort_kind,
            metric.unit,
            str(payload["formula"]),
            encoded,
            checksum,
            now,
        ),
    )
    return key


def _period(observations: Sequence[MetricObservation]) -> tuple[str | None, str | None]:
    if not observations:
        return (None, None)
    values = sorted(item.entry_timestamp for item in observations)
    return (values[0].isoformat(), values[-1].isoformat())


def _duplicate_signal_keys(
    observations: Sequence[MetricObservation],
) -> set[tuple[str, str]]:
    grouped: dict[tuple[str, str], set[str]] = {}
    for item in observations:
        key = (item.signal_projection_key, item.policy_version)
        grouped.setdefault(key, set()).add(item.market_data_fingerprint)
    return {key for key, fingerprints in grouped.items() if len(fingerprints) > 1}


def _leave_one_group_out_sensitivity(
    observations: Sequence[MetricObservation],
    *,
    dimension: str,
) -> dict[str, object]:
    if dimension == "setup" and not any(item.setup for item in observations):
        return {
            "status": "NO_EVIDENCE",
            "reason": "SETUP_NOT_PERSISTED_ON_HISTORICAL_TRADE_SIGNALS",
            "minimum_group_n": 20,
        }
    grouped: dict[str, list[MetricObservation]] = {}
    for item in observations:
        grouped.setdefault(_dimension_value(item, dimension), []).append(item)
    values: list[dict[str, object]] = []
    for group, members in sorted(grouped.items()):
        if len(members) < 20:
            continue
        remaining = [item for item in observations if item not in members]
        remaining_r = [gross_plan_r(item) for item in remaining]
        values.append(
            {
                "excluded_group": group,
                "excluded_n": len(members),
                "remaining_n": len(remaining),
                "remaining_expectancy_r": (
                    sum(remaining_r) / len(remaining_r) if remaining_r else None
                ),
            }
        )
    return {
        "status": "AVAILABLE" if values else "INSUFFICIENT_SAMPLE",
        "minimum_group_n": 20,
        "results": values,
    }


def _safe_observations(
    observations: Sequence[MetricObservation],
) -> tuple[tuple[MetricObservation, ...], dict[str, str]]:
    conflicts = _duplicate_signal_keys(observations)
    excluded: dict[str, str] = {}
    safe: list[MetricObservation] = []
    for item in observations:
        if (item.signal_projection_key, item.policy_version) in conflicts:
            excluded[item.outcome_id] = "MULTIPLE_MARKET_FINGERPRINTS_FOR_SIGNAL"
        else:
            safe.append(item)
    return tuple(safe), excluded


def project_metrics_once(config: MetricProjectionConfig) -> MetricProjectionSummary:
    database = validate_read_model_path(config.sqlite_path, data_root=config.data_root)
    if not database.is_file():
        raise RuntimeError("read model does not exist")
    connection = connect_writer(database, data_root=config.data_root)
    started = datetime.now(tz=UTC)
    try:
        if not schema_is_current(connection):
            raise RuntimeError("read model is not migrated")
        _verify_frozen_policy(connection)
        all_observations = _load_observations(connection)
        observations, fingerprint_conflicts = _safe_observations(all_observations)
        dataset_fingerprint = _dataset_fingerprint(all_observations)
        policy_checksum = frozen_policy_checksum()
        run_id = hashlib.sha256(
            (
                f"metric_run:{METRIC_DEFINITION_VERSION}|{policy_checksum}|"
                f"{dataset_fingerprint}|all-strategies"
            ).encode("utf-8")
        ).hexdigest()
        existing = connection.execute(
            "SELECT run_id FROM metric_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        signals_observed = int(
            connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        )
        decisions = {
            item.outcome_id: classify_eligibility(item) for item in observations
        }
        resolved_count = sum(
            decision.status is EligibilityStatus.ELIGIBLE_RESOLVED
            for decision in decisions.values()
        )
        activated_expired = sum(
            decision.status is EligibilityStatus.ELIGIBLE_ACTIVATED
            for decision in decisions.values()
        )
        excluded_count = len(fingerprint_conflicts) + sum(
            decision.status
            not in {
                EligibilityStatus.ELIGIBLE_RESOLVED,
                EligibilityStatus.ELIGIBLE_ACTIVATED,
                EligibilityStatus.NOT_ACTIVATED,
            }
            for decision in decisions.values()
        )
        completed = datetime.now(tz=UTC).isoformat()
        if existing is not None:
            return MetricProjectionSummary(
                run_id=run_id,
                policy_version=FROZEN_POLICY_VERSION,
                policy_checksum=policy_checksum,
                engine_version=FROZEN_ENGINE_VERSION,
                outcome_dataset_fingerprint=dataset_fingerprint,
                outcomes_observed=len(all_observations),
                signals_observed=signals_observed,
                entry_activated=sum(item.entry_activated for item in observations),
                eligible_resolved=resolved_count,
                eligible_activated_expired=activated_expired,
                excluded=excluded_count,
                cohorts_written=0,
                metric_values_written=0,
                already_present=True,
                completed_at=completed,
            )
        period_start, period_end = _period(observations)
        run_payload = canonical_json(
            {
                "definition_version": METRIC_DEFINITION_VERSION,
                "policy_checksum": policy_checksum,
                "outcome_dataset_fingerprint": dataset_fingerprint,
                "fingerprint_rule": "hash_of_ordered_outcome_identity_evidence_and_levels",
                "expired_r_assigned": False,
                "correlated_or_overlapping_positions_modelled": False,
                "setup_breakdown_available": any(item.setup for item in observations),
            }
        )
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO metric_runs(
                run_id, metric_definition_version, policy_version,
                policy_checksum, engine_version, outcome_dataset_fingerprint,
                strategy_scope, period_start, period_end, outcomes_observed,
                signals_observed, status, run_json, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE', ?, ?, ?)
            """,
            (
                run_id,
                METRIC_DEFINITION_VERSION,
                FROZEN_POLICY_VERSION,
                policy_checksum,
                FROZEN_ENGINE_VERSION,
                dataset_fingerprint,
                "all-strategies",
                period_start,
                period_end,
                len(all_observations),
                signals_observed,
                run_payload,
                started.isoformat(),
                completed,
            ),
        )
        for outcome_id, reason in sorted(fingerprint_conflicts.items()):
            exclusion_id = hashlib.sha256(
                f"metric_exclusion:{run_id}|{outcome_id}|{reason}".encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO metric_exclusions(
                    exclusion_id, run_id, outcome_id, reason_code,
                    exclusion_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    exclusion_id,
                    run_id,
                    outcome_id,
                    reason,
                    canonical_json({"reason_code": reason}),
                    completed,
                ),
            )
        for item in observations:
            decision = decisions[item.outcome_id]
            if decision.status in {
                EligibilityStatus.ELIGIBLE_RESOLVED,
                EligibilityStatus.ELIGIBLE_ACTIVATED,
                EligibilityStatus.NOT_ACTIVATED,
            }:
                continue
            exclusion_id = hashlib.sha256(
                f"metric_exclusion:{run_id}|{item.outcome_id}|{decision.reason_code}".encode(
                    "utf-8"
                )
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO metric_exclusions(
                    exclusion_id, run_id, outcome_id, reason_code,
                    exclusion_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    exclusion_id,
                    run_id,
                    item.outcome_id,
                    decision.reason_code,
                    canonical_json(
                        {
                            "reason_code": decision.reason_code,
                            "eligibility_status": decision.status.value,
                        }
                    ),
                    completed,
                ),
            )
        cohorts_written = values_written = 0
        for cohort in _cohorts(observations):
            fingerprint = _cohort_fingerprint(
                cohort.name,
                cohort.observations,
                cohort.dimension_name,
                cohort.dimension_value,
            )
            cohort_id = hashlib.sha256(
                f"metric_cohort:{run_id}|{cohort.name}|{fingerprint}".encode("utf-8")
            ).hexdigest()
            cohort_start, cohort_end = _period(cohort.observations)
            strategies = sorted(
                {
                    item.strategy_version
                    for item in cohort.observations
                    if item.strategy_version
                }
            )
            filters = {
                "dimension": cohort.dimension_name,
                "value": cohort.dimension_value,
                "policy_version": FROZEN_POLICY_VERSION,
                "engine_version": FROZEN_ENGINE_VERSION,
                "data_quality": "COMPLETE for R metrics",
            }
            included = (
                ["WIN", "LOSS"]
                if cohort.metric_kind == "resolved"
                else (
                    ["WIN", "LOSS", "ACTIVATED_EXPIRED"]
                    if cohort.metric_kind == "activated"
                    else ["ALL_OUTCOME_STATES"]
                )
            )
            excluded = [
                "AMBIGUOUS",
                "NO_MARKET_DATA",
                "INVALID",
                "NON_CANONICAL",
                "CONFLICTING_DATA",
            ]
            sensitivity = (
                {
                    "leave_one_symbol_out": _leave_one_group_out_sensitivity(
                        cohort.observations,
                        dimension="symbol",
                    ),
                    "leave_one_setup_out": _leave_one_group_out_sensitivity(
                        cohort.observations,
                        dimension="setup",
                    ),
                }
                if cohort.name == "ELIGIBLE_RESOLVED"
                else None
            )
            connection.execute(
                """
                INSERT INTO metric_cohorts(
                    cohort_id, run_id, cohort_name, cohort_fingerprint,
                    dimension_name, dimension_value, filters_json,
                    included_statuses_json, excluded_statuses_json,
                    denominator, period_start, period_end, policy_version,
                    engine_version, strategy_identity, evidence_quality,
                    sample_label, cohort_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cohort_id,
                    run_id,
                    cohort.name,
                    fingerprint,
                    cohort.dimension_name,
                    cohort.dimension_value,
                    canonical_json(filters),
                    canonical_json(included),
                    canonical_json(excluded),
                    len(cohort.observations),
                    cohort_start,
                    cohort_end,
                    FROZEN_POLICY_VERSION,
                    FROZEN_ENGINE_VERSION,
                    ",".join(str(item) for item in strategies) or "NO_EVIDENCE",
                    "COMPLETE" if cohort.metric_kind == "resolved" else "MIXED_DECLARED",
                    sample_label(len(cohort.observations)).value,
                    canonical_json(
                        {
                            "return_semantics": (
                                "gross fixed plan target/stop R"
                                if cohort.metric_kind == "resolved"
                                else "no R assigned to activated expired"
                            ),
                            "small_sample_thresholds_visible": True,
                            "sensitivity": sensitivity,
                            "temporal_comparison_rule": (
                                "UTC entry month; no future observations assigned "
                                "to earlier cohorts"
                            ),
                        }
                    ),
                    completed,
                ),
            )
            cohorts_written += 1
            if cohort.metric_kind == "activation":
                metrics = activation_metrics(
                    cohort.observations,
                    total_signals_observed=signals_observed,
                )
            elif cohort.metric_kind == "activated":
                metrics = activated_metrics(cohort.observations)
            else:
                metrics = resolved_metrics(
                    cohort.observations,
                    cohort_fingerprint=fingerprint,
                )
            for metric in metrics:
                definition_key = _register_definition(
                    connection,
                    metric,
                    cohort.metric_kind,
                    completed,
                )
                metric_value_id = hashlib.sha256(
                    f"metric_value:{run_id}|{cohort_id}|{definition_key}".encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO metric_values(
                        metric_value_id, run_id, cohort_id, definition_key,
                        value, numerator, denominator, confidence_lower,
                        confidence_upper, value_json, computed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metric_value_id,
                        run_id,
                        cohort_id,
                        definition_key,
                        metric.value,
                        metric.numerator,
                        metric.denominator,
                        metric.confidence_lower,
                        metric.confidence_upper,
                        canonical_json(
                            {
                                "details": dict(metric.details or {}),
                                "sample_label": sample_label(metric.denominator).value,
                            }
                        ),
                        completed,
                    ),
                )
                values_written += 1
        connection.commit()
        return MetricProjectionSummary(
            run_id=run_id,
            policy_version=FROZEN_POLICY_VERSION,
            policy_checksum=policy_checksum,
            engine_version=FROZEN_ENGINE_VERSION,
            outcome_dataset_fingerprint=dataset_fingerprint,
            outcomes_observed=len(all_observations),
            signals_observed=signals_observed,
            entry_activated=sum(item.entry_activated for item in observations),
            eligible_resolved=resolved_count,
            eligible_activated_expired=activated_expired,
            excluded=excluded_count,
            cohorts_written=cohorts_written,
            metric_values_written=values_written,
            already_present=False,
            completed_at=completed,
        )
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        try:
            finalize_writer(connection)
        finally:
            connection.close()


def _inspect_rows(
    sqlite_path: Path,
    query: str,
    parameters: Sequence[object],
) -> dict[str, object]:
    connection = connect_read_only(sqlite_path)
    try:
        if not schema_is_current(connection):
            return {"status": "schema_unavailable", "items": ()}
        rows = tuple(dict(row) for row in connection.execute(query, parameters))
        return {"status": "ok" if rows else "not_found", "items": rows}
    finally:
        connection.close()


def inspect_metric(sqlite_path: Path, metric_name: str) -> dict[str, object]:
    if not metric_name or len(metric_name) > 100:
        raise ValueError("metric name is invalid")
    return _inspect_rows(
        sqlite_path,
        """
        SELECT d.metric_name, d.definition_version, d.unit, d.formula,
               c.cohort_name, c.dimension_name, c.dimension_value,
               c.denominator, c.period_start, c.period_end, c.sample_label,
               v.value, v.numerator, v.confidence_lower, v.confidence_upper,
               r.policy_version, r.engine_version,
               r.outcome_dataset_fingerprint
        FROM metric_values v
        JOIN metric_definitions d ON d.definition_key=v.definition_key
        JOIN metric_cohorts c ON c.cohort_id=v.cohort_id
        JOIN metric_runs r ON r.run_id=v.run_id
        WHERE d.metric_name=?
        ORDER BY r.completed_at DESC, c.cohort_name, c.dimension_value
        """,
        (metric_name,),
    )


def inspect_cohort(sqlite_path: Path, cohort_id_or_name: str) -> dict[str, object]:
    if not cohort_id_or_name or len(cohort_id_or_name) > 128:
        raise ValueError("cohort identity is invalid")
    return _inspect_rows(
        sqlite_path,
        """
        SELECT c.cohort_id, c.cohort_name, c.dimension_name,
               c.dimension_value, c.denominator, c.period_start,
               c.period_end, c.policy_version, c.engine_version,
               c.strategy_identity, c.evidence_quality, c.sample_label,
               d.metric_name, d.unit, v.value, v.numerator,
               v.denominator AS metric_denominator,
               v.confidence_lower, v.confidence_upper
        FROM metric_cohorts c
        LEFT JOIN metric_values v ON v.cohort_id=c.cohort_id
        LEFT JOIN metric_definitions d ON d.definition_key=v.definition_key
        WHERE c.cohort_id=? OR c.cohort_name=?
        ORDER BY c.dimension_value, d.metric_name
        """,
        (cohort_id_or_name, cohort_id_or_name),
    )


def compare_cohorts(
    sqlite_path: Path,
    left: str,
    right: str,
) -> dict[str, object]:
    if not left or not right or len(left) > 128 or len(right) > 128:
        raise ValueError("cohort identity is invalid")
    connection = connect_read_only(sqlite_path)
    try:
        if not schema_is_current(connection):
            return {"status": "schema_unavailable", "comparisons": ()}
        rows = tuple(
            dict(row)
            for row in connection.execute(
                """
                SELECT d.metric_name, d.unit,
                       lv.value AS left_value, lc.denominator AS left_n,
                       lc.sample_label AS left_sample_label,
                       rv.value AS right_value, rc.denominator AS right_n,
                       rc.sample_label AS right_sample_label,
                       CASE
                         WHEN lv.value IS NULL OR rv.value IS NULL THEN NULL
                         ELSE lv.value-rv.value
                       END AS descriptive_difference
                FROM metric_cohorts lc
                JOIN metric_values lv ON lv.cohort_id=lc.cohort_id
                JOIN metric_definitions d ON d.definition_key=lv.definition_key
                JOIN metric_cohorts rc ON rc.cohort_id<>lc.cohort_id
                JOIN metric_values rv
                  ON rv.cohort_id=rc.cohort_id
                JOIN metric_definitions rd
                  ON rd.definition_key=rv.definition_key
                 AND rd.metric_name=d.metric_name
                 AND rd.cohort_kind=d.cohort_kind
                WHERE (lc.cohort_id=? OR lc.cohort_name=?)
                  AND (rc.cohort_id=? OR rc.cohort_name=?)
                ORDER BY d.metric_name
                """,
                (left, left, right, right),
            )
        )
        return {
            "status": "ok" if rows else "not_found",
            "comparison_type": "descriptive_not_causal",
            "comparisons": rows,
        }
    finally:
        connection.close()
