from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from trading_signals.application.policies.public_safety_policy import POLICY_VERSION
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1


RUNTIME_IDENTITY_SCHEMA = "runtime_identity.v1"
UNKNOWN_VALUES = {"", "unknown", "unset"}
CONFIG_HASH_FIELDS = (
    "adaptive_filter_enabled",
    "adaptive_filter_mode",
    "app_env",
    "edge_activation_mode",
    "entry_timeframe",
    "experiment_id",
    "higher_timeframe",
    "meta_decision_filter_enabled",
    "pair_universe_filter_mode",
    "policy_version",
    "protection_engine_mode",
    "public_short_canary_enabled",
    "relaxed_strategy_gates_enabled",
    "secondary_signal_enabled",
    "selected_engine",
    "short_shadow_mode",
    "strategy_version",
    "trading_commission_r",
    "trading_funding_r",
    "trading_slippage_r",
    "trading_spread_r",
    "use_modular_decision_engine",
)


class RuntimeIdentityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    runtime_identity_schema: str
    git_commit_sha: str
    deployment_id: str
    config_hash: str
    selected_engine: str
    strategy_version: str
    policy_version: str
    experiment_id: str
    runtime_flags: dict[str, Any]
    pid: int
    started_at: str
    release_cwd: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_runtime_identity(
    *,
    root: Path,
    settings: object,
    strict: bool = True,
    pid: int | None = None,
    started_at: str | None = None,
) -> RuntimeIdentity:
    actual_sha = _git_checkout_sha(root)
    configured_sha = _text(getattr(settings, "git_commit_sha", "") or os.getenv("GIT_COMMIT_SHA"))
    if configured_sha and configured_sha != actual_sha:
        raise RuntimeIdentityError(
            f"GIT_COMMIT_SHA mismatch: configured={configured_sha} checkout={actual_sha}"
        )

    actual_engine = "modular" if bool(getattr(settings, "use_modular_decision_engine", False)) else "legacy"
    selected_engine = _validated_code_identity(
        field="selected_engine",
        configured=getattr(settings, "selected_engine", ""),
        actual=actual_engine,
        sources=("SELECTED_ENGINE", "USE_MODULAR_DECISION_ENGINE"),
    )
    strategy_version = _validated_code_identity(
        field="strategy_version",
        configured=getattr(settings, "strategy_version", ""),
        actual=LiquiditySweepMTFV1.strategy_version,
        sources=("STRATEGY_VERSION", "LiquiditySweepMTFV1.strategy_version"),
    )
    policy_version = _validated_code_identity(
        field="policy_version",
        configured=getattr(settings, "policy_version", ""),
        actual=POLICY_VERSION,
        sources=("POLICY_VERSION", "public_safety_policy.POLICY_VERSION"),
    )
    experiment_id = _text(getattr(settings, "experiment_id", "")) or "none"
    deployment_id = _text(getattr(settings, "deployment_id", ""))
    allow_unknown = bool(getattr(settings, "runtime_allow_unknown_identity", False))
    app_env = _text(getattr(settings, "app_env", "")).lower()
    if allow_unknown and app_env not in {"development", "test", "testing"}:
        raise RuntimeIdentityError(
            "RUNTIME_ALLOW_UNKNOWN_IDENTITY is only permitted in development/test"
        )
    if strict and not allow_unknown and _is_unknown(deployment_id):
        raise RuntimeIdentityError(
            "deployment_id is unresolved; consulted DEPLOYMENT_ID"
        )
    if not deployment_id:
        deployment_id = "unknown"

    flags = runtime_flags(settings)
    effective = {
        **flags,
        "selected_engine": selected_engine,
        "strategy_version": strategy_version,
        "policy_version": policy_version,
        "experiment_id": experiment_id,
    }
    config_hash = deterministic_config_hash(effective)
    configured_hash = _text(getattr(settings, "config_hash", "") or os.getenv("CONFIG_HASH"))
    if configured_hash and configured_hash != config_hash:
        raise RuntimeIdentityError(
            f"CONFIG_HASH mismatch: configured={configured_hash} computed={config_hash}"
        )

    identity = RuntimeIdentity(
        runtime_identity_schema=RUNTIME_IDENTITY_SCHEMA,
        git_commit_sha=actual_sha,
        deployment_id=deployment_id,
        config_hash=config_hash,
        selected_engine=selected_engine,
        strategy_version=strategy_version,
        policy_version=policy_version,
        experiment_id=experiment_id,
        runtime_flags=flags,
        pid=pid if pid is not None else os.getpid(),
        started_at=started_at or datetime.now(tz=UTC).isoformat(),
        release_cwd=str(root.resolve()),
    )
    validate_runtime_identity(identity, allow_unknown=allow_unknown)
    return identity


def validate_runtime_identity(
    identity: RuntimeIdentity | Mapping[str, Any],
    *,
    allow_unknown: bool = False,
) -> None:
    values = identity.to_dict() if isinstance(identity, RuntimeIdentity) else dict(identity)
    required = (
        "git_commit_sha",
        "deployment_id",
        "config_hash",
        "experiment_id",
        "pid",
        "started_at",
        "release_cwd",
    )
    for field in required:
        if values.get(field) in {None, ""}:
            raise RuntimeIdentityError(f"{field} is missing from runtime identity")
    if not isinstance(values.get("runtime_flags"), Mapping):
        raise RuntimeIdentityError("runtime_flags is missing from runtime identity")
    for field in ("selected_engine", "strategy_version", "policy_version"):
        if _is_unknown(values.get(field)) and not allow_unknown:
            raise RuntimeIdentityError(
                f"{field} is unresolved; refusing scheduler startup"
            )
    if values.get("runtime_identity_schema") != RUNTIME_IDENTITY_SCHEMA:
        raise RuntimeIdentityError(
            f"unsupported runtime identity schema: {values.get('runtime_identity_schema')!r}"
        )


def heartbeat_with_identity(
    identity: RuntimeIdentity | Mapping[str, Any],
    **state: Any,
) -> dict[str, Any]:
    values = identity.to_dict() if isinstance(identity, RuntimeIdentity) else dict(identity)
    validate_runtime_identity(values)
    return {**state, **values}


def metadata_from_identity(
    identity: RuntimeIdentity | Mapping[str, Any],
    *,
    selected_engine: str | None = None,
    strategy_version: str | None = None,
    experiment_id: str | None = None,
) -> dict[str, Any]:
    values = identity.to_dict() if isinstance(identity, RuntimeIdentity) else dict(identity)
    validate_runtime_identity(values)
    if selected_engine and selected_engine != values["selected_engine"]:
        raise RuntimeIdentityError(
            f"selected_engine runtime mismatch: identity={values['selected_engine']} actual={selected_engine}"
        )
    if strategy_version and strategy_version != values["strategy_version"]:
        raise RuntimeIdentityError(
            f"strategy_version runtime mismatch: identity={values['strategy_version']} actual={strategy_version}"
        )
    if experiment_id is not None:
        values["experiment_id"] = experiment_id
    return values


def deterministic_config_hash(values: Mapping[str, Any]) -> str:
    normalized = {
        field: _normalize(values.get(field))
        for field in CONFIG_HASH_FIELDS
        if field in values
    }
    payload = json.dumps(
        normalized,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def runtime_flags(settings: object) -> dict[str, Any]:
    fields = tuple(
        field
        for field in CONFIG_HASH_FIELDS
        if field not in {"selected_engine", "strategy_version", "policy_version", "experiment_id"}
    )
    return {
        field: _normalize(getattr(settings, field))
        for field in fields
        if hasattr(settings, field)
    }


def _validated_code_identity(
    *,
    field: str,
    configured: object,
    actual: str,
    sources: tuple[str, ...],
) -> str:
    configured_text = _text(configured)
    if configured_text and configured_text != actual:
        raise RuntimeIdentityError(
            f"{field} mismatch: configured={configured_text} actual={actual}; "
            f"consulted {', '.join(sources)}"
        )
    if _is_unknown(actual):
        raise RuntimeIdentityError(
            f"{field} is unresolved; consulted {', '.join(sources)}"
        )
    return actual


def _git_checkout_sha(root: Path) -> str:
    try:
        value = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeIdentityError(
            f"git_commit_sha is unresolved for release {root}"
        ) from exc
    if not value:
        raise RuntimeIdentityError(
            f"git_commit_sha is unresolved for release {root}"
        )
    return value


def _normalize(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        return float(f"{value:.12g}")
    return value


def _is_unknown(value: object) -> bool:
    return _text(value).lower() in UNKNOWN_VALUES


def _text(value: object) -> str:
    return str(value or "").strip()
