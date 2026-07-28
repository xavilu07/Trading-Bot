from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.dashboard.ingestion.projector import (
    ProjectorConfig,
    migrate_read_model,
    project_once,
)
from trading_signals.dashboard.outcomes.projector import (
    OutcomeProjectionConfig,
    default_outcome_policy,
    inspect_outcome,
    project_outcomes_once,
)
from trading_signals.dashboard.outcomes.sources import (
    OutcomeSourceError,
    validate_source_directory,
)
from trading_signals.dashboard.storage import connect_read_only, integrity_check


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest() -> Path:
    return Path("src/trading_signals/dashboard/ingestion/sources.v1.json").resolve()


def _projector_config(root: Path) -> ProjectorConfig:
    data = root / "data"
    return ProjectorConfig(
        data_root=data,
        sqlite_path=root / "runtime/read-model.sqlite",
        manifest_path=_manifest(),
        variables={
            "bot_root": root,
            "data_root": data,
            "reports_root": root / "reports",
            "runtime_root": root / "runtime",
            "active_signal_log": None,
            "scheduler_lock": None,
        },
        selected_sources=("trade_signals",),
    )


def _fixtures(root: Path) -> None:
    _write_json(
        root / "data/trade_signals/2026-07-28/sig-one.json",
        {
            "id": "sig-one",
            "scan_run_id": "run-one",
            "evaluation_id": "eval-one",
            "risk_plan_id": "risk-one",
            "strategy_version": "v1",
            "symbol": "BTCUSDT",
            "decision": "long",
            "status": "valid",
            "entry_timeframe": "1h",
            "created_at": "2026-07-28T10:15:00+00:00",
            "policy_version": "runtime-v1",
        },
    )
    _write_json(
        root / "data/risk_plans/2026-07-28/risk-one.json",
        {
            "id": "risk-one",
            "entry": 100,
            "stop_loss": 95,
            "take_profit": 110,
        },
    )
    _write_json(
        root / "data/market_snapshots/2026-07-28/snapshot-one.json",
        {
            "id": "snapshot-one",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "timestamp": "2026-07-28T11:59:59.999000+00:00",
            "open": 100,
            "high": 111,
            "low": 99,
            "close": 110,
            "volume": 10,
        },
    )


def _source_hashes(data_root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(data_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in data_root.rglob("*")
        if path.is_file()
    }


def _outcome_config(root: Path) -> OutcomeProjectionConfig:
    return OutcomeProjectionConfig(
        data_root=root / "data",
        sqlite_path=root / "runtime/read-model.sqlite",
        risk_plans_root=root / "data/risk_plans",
        market_snapshots_root=root / "data/market_snapshots",
        policy=default_outcome_policy(horizon_candles=1),
        as_of=datetime(2026, 7, 28, 13, tzinfo=UTC),
    )


def test_outcomes_projection_is_idempotent_and_sources_are_untouched(
    tmp_path: Path,
) -> None:
    _fixtures(tmp_path)
    projector = _projector_config(tmp_path)
    migrate_read_model(projector)
    project_once(projector)
    source_hashes = _source_hashes(tmp_path / "data")
    config = _outcome_config(tmp_path)
    first = project_outcomes_once(config)
    second = project_outcomes_once(config)
    assert first.inserted == 1
    assert first.status_counts == {"WIN": 1}
    assert second.inserted == 0
    assert second.already_present == 1
    assert _source_hashes(tmp_path / "data") == source_hashes
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM outcome_evidence").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM outcome_policies").fetchone()[0] == 1
        enriched = connection.execute(
            """
            SELECT entry_activated, entry_activated_at,
                   entry_activation_candle_open, candles_until_entry,
                   candles_after_entry, entry_lifecycle_status,
                   eligibility_status
            FROM signal_outcomes
            """
        ).fetchone()
        assert tuple(enriched) == (
            1,
            "2026-07-28T11:00:00+00:00",
            "2026-07-28T11:00:00+00:00",
            1,
            0,
            "RESOLVED_WIN",
            "ELIGIBLE_RESOLVED",
        )
        assert integrity_check(connection) == ("ok",)
    finally:
        connection.close()


def test_changed_market_fingerprint_creates_separate_evidence_not_overwrite(
    tmp_path: Path,
) -> None:
    _fixtures(tmp_path)
    projector = _projector_config(tmp_path)
    migrate_read_model(projector)
    project_once(projector)
    config = _outcome_config(tmp_path)
    project_outcomes_once(config)
    snapshot = tmp_path / "data/market_snapshots/2026-07-28/snapshot-one.json"
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["close"] = 109
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    project_outcomes_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(DISTINCT market_data_fingerprint) FROM signal_outcomes"
        ).fetchone()[0] == 2
    finally:
        connection.close()


def test_inspect_outcome_is_read_only_and_redacted(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    projector = _projector_config(tmp_path)
    migrate_read_model(projector)
    project_once(projector)
    config = _outcome_config(tmp_path)
    project_outcomes_once(config)
    before = hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest()
    result = inspect_outcome(config.sqlite_path, "sig-one")
    after = hashlib.sha256(config.sqlite_path.read_bytes()).hexdigest()
    assert result["status"] == "ok"
    serialized = json.dumps(result)
    assert "/root/" not in serialized
    assert before == after


def test_source_paths_must_be_inside_configured_data_root(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        validate_source_directory(outside, data_root=data)
    except OutcomeSourceError as exc:
        assert exc.code == "SOURCE_PATH_OUTSIDE_DATA_ROOT"
    else:
        raise AssertionError("outside source path was accepted")


def test_signal_without_risk_levels_is_explicitly_invalid(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    risk = tmp_path / "data/risk_plans/2026-07-28/risk-one.json"
    risk.unlink()
    projector = _projector_config(tmp_path)
    migrate_read_model(projector)
    project_once(projector)
    summary = project_outcomes_once(_outcome_config(tmp_path))
    assert summary.missing_levels == 1
    assert summary.status_counts == {"INVALID": 1}
    connection = connect_read_only(tmp_path / "runtime/read-model.sqlite")
    try:
        row = connection.execute(
            "SELECT terminal_status, entry_price, stop_price, target_price "
            "FROM signal_outcomes"
        ).fetchone()
        assert tuple(row) == ("INVALID", None, None, None)
    finally:
        connection.close()
