from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from trading_signals.agents.qic_event_detector import detect_qic_events
from trading_signals.data.canonical_trade_source import (
    TradeUniverse,
    TradingCostConfig,
    compute_trade_metrics,
    deduplicate_statistical_rows,
    load_canonical_closed_trades,
    load_counterfactual_trades,
    load_shadow_trades,
    load_trade_universe,
    normalize_trade_row,
    runtime_trace,
)
from trading_signals.memory.edge_memory import build_edge_memory
from trading_signals.runtime.scheduler_guard import DuplicateSchedulerError, SchedulerInstanceGuard


def test_productive_kpis_exclude_rejected_and_shadow(tmp_path: Path) -> None:
    _write_csv(tmp_path / "paper_trading/trades.csv", [_row(universe="accepted", result_r="1")])
    _write_csv(tmp_path / "shadow_relaxation/trades.csv", [_row(universe="shadow", result_r="50")])
    _write_jsonl(tmp_path / "bot_activity/signals_log.jsonl", [{**_row(result_r="-50"), "status": "rejected"}])
    accepted = load_canonical_closed_trades(tmp_path)
    assert len(accepted) == 1
    assert compute_trade_metrics(accepted)["net_total_r"] == 1
    assert len(load_shadow_trades(tmp_path, closed_only=True)) == 1


def test_published_requires_confirmed_delivery_timestamp(tmp_path: Path) -> None:
    intended = _row(public_published="true", published_at="")
    confirmed = _row(symbol="ETHUSDT", public_published="true", published_at="2026-01-01T01:00:00+00:00")
    _write_csv(tmp_path / "paper_trading/trades.csv", [intended, confirmed])
    published = load_trade_universe(tmp_path, TradeUniverse.PUBLISHED, closed_only=True)
    assert [row["symbol"] for row in published] == ["ETHUSDT"]


def test_costs_convert_gross_to_net() -> None:
    row = normalize_trade_row(
        _row(result_r="2"),
        source="test",
        source_universe=TradeUniverse.ACCEPTED,
        cost_config=TradingCostConfig(commission_r=0.1, spread_r=0.2, slippage_r=0.05, funding_r=0.05),
    )
    assert row is not None
    # New rows signal that costs are applicable by carrying at least one persisted cost field.
    row = normalize_trade_row(
        {**_row(result_r="2"), "commission": "0.1"},
        source="test",
        source_universe=TradeUniverse.ACCEPTED,
        cost_config=TradingCostConfig(commission_r=0.1, spread_r=0.2, slippage_r=0.05, funding_r=0.05),
    )
    assert row is not None
    assert row["total_cost"] == pytest.approx(0.4)
    assert row["net_result_r"] == pytest.approx(1.6)


def test_open_rows_are_excluded_and_expirations_separate() -> None:
    rows = [
        normalize_trade_row(_row(status="open", result_r="0"), source="x", source_universe=TradeUniverse.ACCEPTED),
        normalize_trade_row(_row(symbol="ETHUSDT", status="expired", result_r="0"), source="x", source_universe=TradeUniverse.ACCEPTED),
        normalize_trade_row(_row(symbol="SOLUSDT", status="tp2_hit", result_r="2"), source="x", source_universe=TradeUniverse.ACCEPTED),
    ]
    metrics = compute_trade_metrics([row for row in rows if row])
    assert metrics["closed_trades"] == 2
    assert metrics["outcome_trades"] == 1
    assert metrics["expired_trades"] == 1
    assert metrics["open_trades_excluded"] == 1


def test_same_statistical_key_is_deduplicated_to_latest() -> None:
    first = normalize_trade_row(_row(updated_at="2026-01-01T01:00:00+00:00"), source="x", source_universe=TradeUniverse.ACCEPTED)
    second = normalize_trade_row(_row(updated_at="2026-01-01T02:00:00+00:00", result_r="2"), source="x", source_universe=TradeUniverse.ACCEPTED)
    assert first and second
    rows = deduplicate_statistical_rows([first, second])
    assert len(rows) == 1
    assert rows[0]["gross_result_r"] == 2


def test_version_or_experiment_produces_independent_observation() -> None:
    first = normalize_trade_row(_row(), source="x", source_universe=TradeUniverse.ACCEPTED)
    second = normalize_trade_row(_row(strategy_version="v2"), source="x", source_universe=TradeUniverse.ACCEPTED)
    third = normalize_trade_row(_row(experiment_id="exp-2"), source="x", source_universe=TradeUniverse.ACCEPTED)
    assert len(deduplicate_statistical_rows([row for row in (first, second, third) if row])) == 3


def test_historical_rows_are_conservative_and_not_claimed_published(tmp_path: Path) -> None:
    historical = {"symbol": "BTCUSDT", "status": "tp2_hit", "result_r": "1", "opened_at": "2025-01-01T00:00:00+00:00"}
    _write_csv(tmp_path / "paper_trading/trades.csv", [historical])
    row = load_canonical_closed_trades(tmp_path)[0]
    assert row["universe"] == "accepted"
    assert row["public_published"] is False
    assert row["strategy_version"] == "unknown"
    assert row["git_commit_sha"] == "unknown"
    assert row["costs_known"] is False


def test_metadata_is_complete_for_new_normalized_row() -> None:
    row = normalize_trade_row(_row(), source="x", source_universe=TradeUniverse.ACCEPTED)
    assert row is not None
    required = {
        "strategy_version", "git_commit_sha", "config_hash", "runtime_flags",
        "deployment_id", "selected_engine", "policy_version", "experiment_id",
        "universe", "accepted", "public_published", "created_at", "accepted_at", "published_at",
    }
    assert required <= row.keys()


def test_runtime_trace_identifies_commit_config_and_deployment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_COMMIT_SHA", "abc123")
    trace = runtime_trace(root=tmp_path, settings=type("S", (), {"app_env": "test"})(), deployment_id="deploy-7")
    assert trace["git_commit_sha"] == "abc123"
    assert trace["deployment_id"] == "deploy-7"
    assert len(trace["config_hash"]) == 64


def test_scheduler_guard_detects_duplicate(tmp_path: Path) -> None:
    first = SchedulerInstanceGuard(tmp_path / "scheduler.lock", {"git_commit_sha": "abc"}).acquire()
    try:
        with pytest.raises(DuplicateSchedulerError):
            SchedulerInstanceGuard(tmp_path / "scheduler.lock", {"git_commit_sha": "def"}).acquire()
    finally:
        first.release()


def test_edge_memory_and_qic_use_accepted_only(tmp_path: Path) -> None:
    accepted = [_row(symbol=f"S{idx}", result_r="1") for idx in range(2)]
    accepted.append(_row(symbol="LOSS", result_r="-1", status="sl_hit"))
    rejected = _row(symbol="REJECTED", universe="rejected", result_r="-100", status="sl_hit")
    _write_csv(tmp_path / "paper_trading/trades.csv", [*accepted, rejected])
    memory = build_edge_memory(tmp_path, min_sample_size=1)
    assert memory["universe"] == "accepted"
    assert memory["closed_trades"] == 3
    assert [row["symbol"] for row in load_counterfactual_trades(tmp_path, closed_only=True)] == ["REJECTED"]
    qic = detect_qic_events(trades_path=tmp_path / "paper_trading/trades.csv")
    assert qic["profit_factor"] == 2.0


def _row(**updates: str) -> dict[str, str]:
    row = {
        "trade_id": "trade-1",
        "symbol": "BTCUSDT",
        "direction": "long",
        "status": "tp2_hit",
        "result_r": "1",
        "opened_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T01:00:00+00:00",
        "closed_at": "2026-01-01T01:00:00+00:00",
        "timeframe": "1h",
        "candle_close": "2026-01-01T00:00:00+00:00",
        "selected_engine": "legacy",
        "strategy_version": "v1",
        "policy_version": "v1",
        "experiment_id": "none",
        "universe": "accepted",
        "accepted": "true",
        "public_published": "false",
        "published_at": "",
        "created_at": "2026-01-01T00:00:00+00:00",
        "accepted_at": "2026-01-01T00:00:00+00:00",
    }
    row.update(updates)
    return row


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
