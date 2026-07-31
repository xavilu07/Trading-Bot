from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_signals.app.cli import save_scheduler_heartbeat
from trading_signals.runtime.identity import (
    RUNTIME_IDENTITY_SCHEMA,
    RuntimeIdentityError,
    build_runtime_identity,
    deterministic_config_hash,
    heartbeat_with_identity,
    metadata_from_identity,
    validate_runtime_identity,
)
from trading_signals.runtime.scheduler_guard import DuplicateSchedulerError, SchedulerInstanceGuard


REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "app_env": "production",
        "deployment_id": "deploy-regression",
        "git_commit_sha": "",
        "selected_engine": "",
        "strategy_version": "",
        "policy_version": "",
        "experiment_id": "none",
        "config_hash": "",
        "runtime_allow_unknown_identity": False,
        "use_modular_decision_engine": False,
        "entry_timeframe": "15m",
        "higher_timeframe": "1h",
        "trading_commission_r": 0.02,
        "trading_spread_r": 0.01,
        "trading_slippage_r": 0.01,
        "trading_funding_r": 0.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _identity(**settings: object):
    return build_runtime_identity(
        root=REPO_ROOT,
        settings=_settings(**settings),
        pid=4242,
        started_at="2026-07-23T20:00:00+00:00",
    )


def test_failed_deployment_regression_derives_all_critical_fields() -> None:
    identity = _identity()
    assert identity.selected_engine == "legacy"
    assert identity.strategy_version == "v1"
    assert identity.policy_version == "v1"
    assert identity.runtime_identity_schema == RUNTIME_IDENTITY_SCHEMA


def test_explicit_configuration_flows_to_runtime_contract() -> None:
    identity = _identity(
        selected_engine="legacy",
        strategy_version="v1",
        policy_version="v1",
        experiment_id="baseline",
    )
    assert identity.deployment_id == "deploy-regression"
    assert identity.experiment_id == "baseline"
    assert identity.pid == 4242
    assert identity.release_cwd == str(REPO_ROOT)


def test_configured_identity_must_match_effective_code_and_engine() -> None:
    with pytest.raises(RuntimeIdentityError, match="selected_engine mismatch"):
        _identity(selected_engine="modular")
    with pytest.raises(RuntimeIdentityError, match="strategy_version mismatch"):
        _identity(strategy_version="arbitrary")
    with pytest.raises(RuntimeIdentityError, match="policy_version mismatch"):
        _identity(policy_version="arbitrary")


def test_lock_serializes_complete_identity_and_blocks_second_scheduler(tmp_path: Path) -> None:
    identity = _identity().to_dict()
    lock = tmp_path / "scheduler.lock"
    first = SchedulerInstanceGuard(lock, identity).acquire()
    try:
        payload = json.loads(lock.read_text(encoding="utf-8"))
        for field in (
            "selected_engine",
            "strategy_version",
            "policy_version",
            "git_commit_sha",
            "deployment_id",
            "config_hash",
        ):
            assert payload[field] == identity[field]
        assert payload["runtime_identity_schema"] == RUNTIME_IDENTITY_SCHEMA
        with pytest.raises(DuplicateSchedulerError):
            SchedulerInstanceGuard(lock, identity).acquire()
    finally:
        first.release()


def test_initial_and_repeated_heartbeats_preserve_identity(tmp_path: Path) -> None:
    identity = _identity()
    first = heartbeat_with_identity(identity, cycle_number=0, status="starting")
    second = heartbeat_with_identity(identity, **{**first, "cycle_number": 1, "status": "ok"})
    third = heartbeat_with_identity(identity, **{**second, "cycle_number": 2, "status": "ok"})
    save_scheduler_heartbeat(tmp_path / "heartbeat.json", third)
    persisted = json.loads((tmp_path / "heartbeat.json").read_text(encoding="utf-8"))
    for field, value in identity.to_dict().items():
        assert first[field] == value
        assert second[field] == value
        assert persisted[field] == value
    assert persisted["cycle_number"] == 2


def test_invalid_identity_fails_before_lock_and_cannot_make_healthy_heartbeat(tmp_path: Path) -> None:
    invalid = _identity().to_dict()
    invalid["strategy_version"] = ""
    lock = tmp_path / "scheduler.lock"
    with pytest.raises(RuntimeIdentityError, match="strategy_version"):
        SchedulerInstanceGuard(lock, invalid).acquire()
    assert not lock.exists()
    with pytest.raises(RuntimeIdentityError, match="strategy_version"):
        heartbeat_with_identity(invalid, status="ok")


def test_production_requires_deployment_and_dev_escape_is_explicit() -> None:
    with pytest.raises(RuntimeIdentityError, match="deployment_id"):
        _identity(deployment_id="")
    with pytest.raises(RuntimeIdentityError, match="only permitted"):
        _identity(runtime_allow_unknown_identity=True)
    development = _identity(
        app_env="development",
        deployment_id="",
        runtime_allow_unknown_identity=True,
    )
    assert development.deployment_id == "unknown"
    assert development.selected_engine != "unknown"


def test_git_sha_and_config_hash_are_assertions_not_overrides() -> None:
    actual = _identity()
    with pytest.raises(RuntimeIdentityError, match="GIT_COMMIT_SHA mismatch"):
        _identity(git_commit_sha="0" * 40)
    with pytest.raises(RuntimeIdentityError, match="CONFIG_HASH mismatch"):
        _identity(config_hash="0" * 64)
    asserted = _identity(git_commit_sha=actual.git_commit_sha, config_hash=actual.config_hash)
    assert asserted.git_commit_sha == actual.git_commit_sha
    assert asserted.config_hash == actual.config_hash


def test_config_hash_is_deterministic_and_ignores_identity_ephemera() -> None:
    left = {
        "selected_engine": "legacy",
        "strategy_version": "v1",
        "policy_version": "v1",
        "experiment_id": "none",
        "entry_timeframe": "15m",
        "deployment_id": "one",
        "CONFIG_HASH": "recursive",
    }
    right = {
        "entry_timeframe": "15m",
        "experiment_id": "none",
        "policy_version": "v1",
        "strategy_version": "v1",
        "selected_engine": "legacy",
        "deployment_id": "two",
    }
    assert deterministic_config_hash(left) == deterministic_config_hash(right)


def test_signal_and_trade_metadata_reuse_the_same_runtime_identity() -> None:
    identity = _identity()
    signal = metadata_from_identity(
        identity,
        selected_engine="legacy",
        strategy_version="v1",
    )
    trade = metadata_from_identity(
        identity,
        selected_engine="legacy",
        strategy_version="v1",
    )
    assert signal == trade == identity.to_dict()


def test_environment_names_are_loaded_by_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from trading_signals.app.settings import Settings

    expected = {
        "SELECTED_ENGINE": "legacy",
        "STRATEGY_VERSION": "v1",
        "POLICY_VERSION": "v1",
        "DEPLOYMENT_ID": "deploy-env",
        "EXPERIMENT_ID": "baseline",
    }
    for name, value in expected.items():
        monkeypatch.setenv(name, value)
    settings = Settings()
    assert settings.selected_engine == "legacy"
    assert settings.strategy_version == "v1"
    assert settings.policy_version == "v1"
    assert settings.deployment_id == "deploy-env"
    assert settings.experiment_id == "baseline"
