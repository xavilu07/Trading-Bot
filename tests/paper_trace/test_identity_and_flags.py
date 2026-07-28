from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_signals.app.settings import Settings
from trading_signals.domain.entities.trade_signal import TradeSignal
from trading_signals.paper_trace.contracts import TargetRole, TraceContractError
from trading_signals.paper_trace.identity import build_prospective_identity, setup_identity
from trading_signals.paper_trace.sanitize import setup_parameters_hash
from trading_signals.paper_trace.service import (
    PaperTraceConfigurationError,
    build_paper_trace_service,
)


def _objects(tmp_path: Path):
    signal = SimpleNamespace(
        id="sig-1",
        created_at="2026-01-01T10:01:00+00:00",
        symbol="BTCUSDT",
        decision="long",
        entry_timeframe="1h",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        git_commit_sha="a" * 40,
        policy_version="v1",
        scan_run_id="run-1",
    )
    evaluation = SimpleNamespace(created_at="2026-01-01T10:00:00+00:00")
    risk = SimpleNamespace(entry=100.0, stop_loss=95.0, take_profit=110.0)
    entry = SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp="2026-01-01T10:00:00+00:00",
        open=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
        trend="up",
        market_structure="bullish",
        liquidity_sweep="bullish",
        metadata={"rsi": 50.0, "api_token": "must-not-hash"},
    )
    higher = SimpleNamespace(**{**entry.__dict__, "timeframe": "4h"})
    settings = Settings(
        data_storage_path=tmp_path / "data",
        paper_trading_timeout_candles=24,
    )
    runtime = {"config_hash": "b" * 64}
    return signal, evaluation, risk, entry, higher, settings, runtime


def test_setup_identity_comes_from_real_origin_marker() -> None:
    assert setup_identity("MAIN_SIGNAL") == ("liquidity-sweep-primary", "v1")
    assert setup_identity("SECONDARY_SIGNAL") == (
        "break-of-structure-secondary",
        "v1",
    )
    with pytest.raises(TraceContractError, match="SETUP_ID_UNDEMONSTRATED"):
        setup_identity("SIGNAL")


def test_prospective_identity_persists_final_target_and_versions(tmp_path: Path) -> None:
    signal, evaluation, risk, entry, higher, settings, runtime = _objects(tmp_path)
    identity = build_prospective_identity(
        signal=signal,
        risk_plan=risk,
        evaluation=evaluation,
        entry_snapshot=entry,
        higher_snapshot=higher,
        setup_type="MAIN_SIGNAL",
        settings=settings,
        runtime_identity=runtime,
    )
    assert identity.setup_id == "liquidity-sweep-primary"
    assert identity.target_role is TargetRole.FINAL_TARGET
    assert identity.target_index == 2
    assert identity.strategy_version == "v1"
    assert identity.fee_model_id == "NO_FEE_MODEL"
    assert identity.slippage_model_id == "NO_SLIPPAGE_MODEL"


def test_setup_hash_is_deterministic_and_excludes_secrets() -> None:
    public = {"entry_timeframe": "1h", "min_rr": 2.0}
    with_secret = {**public, "api_key": "private", "telegram_token": "private"}
    assert setup_parameters_hash(public) == setup_parameters_hash(with_secret)


def test_disabled_flag_has_zero_filesystem_effect(tmp_path: Path) -> None:
    settings = Settings(
        data_storage_path=tmp_path / "data",
        paper_trace_enabled=False,
        paper_trace_store_path=tmp_path / "runtime/trace.jsonl",
    )
    before = tuple(tmp_path.rglob("*"))
    assert build_paper_trace_service(settings) is None
    assert tuple(tmp_path.rglob("*")) == before


def test_enabled_without_safe_path_fails_closed(tmp_path: Path) -> None:
    settings = Settings(
        data_storage_path=tmp_path / "data",
        paper_trace_enabled=True,
        paper_trace_store_path=None,
    )
    with pytest.raises(PaperTraceConfigurationError, match="PAPER_TRACE_STORE_PATH_REQUIRED"):
        build_paper_trace_service(settings)
    assert not (tmp_path / "data").exists()


def test_enabled_never_falls_back_to_data_root(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    settings = Settings(
        data_storage_path=data,
        paper_trace_enabled=True,
        paper_trace_store_path=data / "trace.jsonl",
    )
    with pytest.raises(PaperTraceConfigurationError, match="PAPER_TRACE_STORE_PATH_UNSAFE"):
        build_paper_trace_service(settings)
    assert not (data / "trace.jsonl").exists()


def test_historical_trade_signal_schema_remains_readable() -> None:
    historical = TradeSignal(
        id="sig-old",
        scan_run_id="run-old",
        evaluation_id="eval-old",
        risk_plan_id=None,
        strategy_id="legacy",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision="no_trade",
        status="rejected",
        dedupe_key="legacy-key",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert historical.schema_version == "1.0"
    assert not hasattr(historical, "setup_id")
