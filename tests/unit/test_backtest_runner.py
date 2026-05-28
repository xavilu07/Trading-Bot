from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.run_backtest_runner import BacktestConfig, load_real_trades, run_backtest_runner


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_backtest_runner_handles_empty_data(tmp_path: Path) -> None:
    result = run_backtest_runner(data_path=tmp_path / "data", reports_path=tmp_path / "reports")

    assert result["report"]["trades_loaded"] == 0
    assert (tmp_path / "reports" / "backtest_runner_report.json").exists()
    assert (tmp_path / "reports" / "backtest_runner_report.csv").exists()
    assert (tmp_path / "reports" / "backtest_runner_summary.md").exists()


def test_backtest_runner_baseline_counts_real_closed_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {"symbol": "BTCUSDT", "direction": "long", "status": "tp_hit", "result_r": "2", "closed_at": "2026-01-01T10:00:00+00:00"},
            {"symbol": "ETHUSDT", "direction": "short", "status": "sl_hit", "result_r": "-1", "closed_at": "2026-01-01T11:00:00+00:00"},
            {"symbol": "SOLUSDT", "direction": "long", "status": "open", "result_r": "5", "opened_at": "2026-01-01T12:00:00+00:00"},
        ],
    )

    trades = load_real_trades(data_path)
    result = run_backtest_runner(data_path=data_path, reports_path=tmp_path / "reports")
    raw = _layer(result, "raw_strategy")

    assert len(trades) == 2
    assert raw["metrics"]["trades_evaluated"] == 2
    assert raw["metrics"]["trades_accepted"] == 2
    assert raw["metrics"]["total_r"] == 1.0


def test_public_safety_rejects_bad_public_context_and_improves_loss(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "OVERLAP",
                "entry_context": "BREAKOUT",
                "trade_location": "mid_range",
                "status": "tp_hit",
                "result_r": "2",
                "closed_at": "2026-01-01T10:00:00+00:00",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "RANGING",
                "session": "NEW_YORK",
                "entry_context": "CHOPPY_RANGE",
                "trade_location": "premium_zone",
                "avoidance_warnings": '["low_volume"]',
                "status": "sl_hit",
                "result_r": "-1",
                "closed_at": "2026-01-01T11:00:00+00:00",
            },
        ],
    )

    result = run_backtest_runner(data_path=data_path, reports_path=tmp_path / "reports")
    safety = _layer(result, "public_safety_policy")

    assert safety["metrics"]["trades_accepted"] == 1
    assert safety["metrics"]["trades_rejected"] == 1
    assert safety["metrics"]["total_r"] == 2.0
    assert safety["metrics"]["delta_total_r_vs_baseline"] == 1.0
    assert any(item["reason"] == "market_regime_ranging" for item in safety["metrics"]["top_rejection_reasons"])
    assert safety["top_improved_contexts"]


def test_public_short_canary_allows_only_specific_short_subset(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "AVAXUSDT",
                "direction": "short",
                "setup_type": "MAIN_SIGNAL",
                "score": "75",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "PULLBACK",
                "trade_location": "mid_range",
                "status": "tp_hit",
                "result_r": "2",
                "closed_at": "2026-01-01T10:00:00+00:00",
            },
            {
                "symbol": "DOGEUSDT",
                "direction": "short",
                "setup_type": "MAIN_SIGNAL",
                "score": "60",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "PULLBACK",
                "trade_location": "mid_range",
                "status": "tp_hit",
                "result_r": "2",
                "closed_at": "2026-01-01T11:00:00+00:00",
            },
        ],
    )

    result = run_backtest_runner(data_path=data_path, reports_path=tmp_path / "reports")
    canary = _layer(result, "public_short_canary")

    assert canary["metrics"]["trades_accepted"] == 1
    assert canary["metrics"]["trades_rejected"] == 1
    assert canary["metrics"]["total_r"] == 2.0


def test_kill_switch_blocks_after_prior_losses(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {"symbol": "A", "direction": "long", "status": "sl_hit", "result_r": "-1", "closed_at": "2026-01-01T10:00:00+00:00"},
            {"symbol": "B", "direction": "long", "status": "sl_hit", "result_r": "-1", "closed_at": "2026-01-01T11:00:00+00:00"},
            {"symbol": "C", "direction": "long", "status": "tp_hit", "result_r": "2", "closed_at": "2026-01-01T12:00:00+00:00"},
        ],
    )

    result = run_backtest_runner(
        data_path=data_path,
        reports_path=tmp_path / "reports",
        config=BacktestConfig(max_daily_loss_r=2.0, max_consecutive_losses=2, kill_switch_cooldown_hours=12),
    )
    kill_switch = _layer(result, "kill_switch_risk_guard")

    assert kill_switch["metrics"]["trades_accepted"] == 1
    assert kill_switch["metrics"]["trades_rejected"] == 2
    assert any(item["reason"] == "cooldown_active" for item in kill_switch["metrics"]["top_rejection_reasons"])


def test_backtest_runner_writes_expected_csv_and_json(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [{"symbol": "BTCUSDT", "direction": "long", "status": "tp_hit", "result_r": "1", "closed_at": "2026-01-01T10:00:00+00:00"}],
    )

    result = run_backtest_runner(data_path=data_path, reports_path=tmp_path / "reports")
    csv_rows = list(csv.DictReader((tmp_path / "reports" / "backtest_runner_report.csv").open(encoding="utf-8")))
    json_report = json.loads((tmp_path / "reports" / "backtest_runner_report.json").read_text(encoding="utf-8"))

    assert result["csv_path"].endswith("backtest_runner_report.csv")
    assert len(csv_rows) == 6
    assert json_report["baseline_layer"] == "raw_strategy"


def _layer(result: dict[str, object], name: str) -> dict[str, object]:
    report = result["report"]
    assert isinstance(report, dict)
    for layer in report["layers"]:
        if layer["layer"] == name:
            return layer
    raise AssertionError(f"missing layer {name}")
