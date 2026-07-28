from __future__ import annotations

from datetime import UTC, datetime
from typing import Mapping

from trading_signals.paper_trace.contracts import (
    ProspectiveSignalIdentity,
    TargetRole,
    TraceContractError,
)
from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
    TRACE_MODEL_VERSION,
    trace_policy_checksum,
)
from trading_signals.paper_trace.sanitize import setup_parameters_hash, stable_hash


_SETUP_IDENTITIES = {
    "MAIN_SIGNAL": ("liquidity-sweep-primary", "v1"),
    "SECONDARY_SIGNAL": ("break-of-structure-secondary", "v1"),
}


def setup_identity(setup_type: str) -> tuple[str, str]:
    try:
        return _SETUP_IDENTITIES[setup_type]
    except KeyError as exc:
        raise TraceContractError("SETUP_ID_UNDEMONSTRATED") from exc


def decision_policy_identity(policy_version: str) -> tuple[str, str]:
    if policy_version == "v1":
        return "public-safety-policy", policy_version
    if policy_version == "relaxed_public_safety_v2":
        return "relaxed-public-safety-policy", policy_version
    raise TraceContractError("DECISION_POLICY_ID_UNDEMONSTRATED")


def market_context_fingerprint(entry_snapshot: object, higher_snapshot: object) -> str:
    def public(snapshot: object) -> dict[str, object]:
        metadata = getattr(snapshot, "metadata", {})
        safe_metadata = {
            key: value
            for key, value in dict(metadata).items()
            if key
            in {
                "break_of_structure",
                "directional_liquidity_level",
                "directional_liquidity_side",
                "nearest_liquidity_level",
                "nearest_liquidity_side",
                "rsi",
                "volume_ratio_vs_average_20",
            }
        }
        return {
            "symbol": getattr(snapshot, "symbol", None),
            "timeframe": getattr(snapshot, "timeframe", None),
            "timestamp": getattr(snapshot, "timestamp", None),
            "open": getattr(snapshot, "open", None),
            "high": getattr(snapshot, "high", None),
            "low": getattr(snapshot, "low", None),
            "close": getattr(snapshot, "close", None),
            "source": getattr(snapshot, "source", None),
            "trend": getattr(snapshot, "trend", None),
            "market_structure": getattr(snapshot, "market_structure", None),
            "liquidity_sweep": getattr(snapshot, "liquidity_sweep", None),
            "metadata": safe_metadata,
        }

    return stable_hash(
        {"entry": public(entry_snapshot), "higher": public(higher_snapshot)},
        namespace="paper_trace_market_context.v1",
    )


def build_prospective_identity(
    *,
    signal: object,
    risk_plan: object,
    evaluation: object,
    entry_snapshot: object,
    higher_snapshot: object,
    setup_type: str,
    settings: object,
    runtime_identity: Mapping[str, object],
) -> ProspectiveSignalIdentity:
    setup_id, setup_version = setup_identity(setup_type)
    policy_id, policy_version = decision_policy_identity(str(getattr(signal, "policy_version")))
    strategy_commit = str(getattr(signal, "git_commit_sha", "")).lower()
    if len(strategy_commit) != 40:
        raise TraceContractError("STRATEGY_COMMIT_UNAVAILABLE")
    parameters = {
        key: getattr(settings, key)
        for key in (
            "atr_min_threshold",
            "entry_timeframe",
            "higher_timeframe",
            "max_distance_to_liquidity_atr",
            "min_body_ratio",
            "min_rr",
            "relaxed_strategy_gates_enabled",
            "setup_score_threshold",
        )
    }
    decision_at = str(getattr(evaluation, "created_at"))
    created_at = str(getattr(signal, "created_at"))
    return ProspectiveSignalIdentity(
        signal_id=str(getattr(signal, "id")),
        signal_schema_version="paper.signal.identity.v1",
        created_at=datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(UTC),
        decision_at=datetime.fromisoformat(decision_at.replace("Z", "+00:00")).astimezone(UTC),
        symbol=str(getattr(signal, "symbol")),
        direction=str(getattr(signal, "decision")),
        timeframe=str(getattr(signal, "entry_timeframe")),
        strategy_id=str(getattr(signal, "strategy_id")),
        strategy_version=str(getattr(signal, "strategy_version")),
        strategy_commit=strategy_commit,
        setup_id=setup_id,
        setup_version=setup_version,
        setup_parameters_hash=setup_parameters_hash(parameters),
        policy_id=policy_id,
        policy_version=policy_version,
        fill_policy_id=DEFAULT_FILL_POLICY_ID,
        fill_policy_version=trace_policy_checksum(),
        expiry_policy_id=DEFAULT_EXPIRY_POLICY_ID,
        engine_version=TRACE_MODEL_VERSION,
        config_hash=str(runtime_identity.get("config_hash", "")),
        market_context_fingerprint=market_context_fingerprint(
            entry_snapshot,
            higher_snapshot,
        ),
        entry_price=float(getattr(risk_plan, "entry")),
        stop_price=float(getattr(risk_plan, "stop_loss")),
        target_price=float(getattr(risk_plan, "take_profit")),
        target_role=TargetRole.FINAL_TARGET,
        target_index=2,
        horizon_candles=int(getattr(settings, "paper_trading_timeout_candles")),
        source_cycle_id=str(getattr(signal, "scan_run_id")),
        source_agent_decision_id=None,
        correlation_group_id=None,
    )
