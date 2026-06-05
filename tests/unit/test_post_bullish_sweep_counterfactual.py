from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.post_bullish_sweep_counterfactual import (
    analyze_post_bullish_sweep_counterfactual,
    classify_loss_component,
    write_post_bullish_sweep_counterfactual_report,
)


def test_post_counterfactual_removes_all_bullish_sweep_rows(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", "long", -1.0, liquidity_context="sweep:bullish_sweep"),
            _trade(3, "SOLUSDT", "short", 1.5, liquidity_sweep="bearish_sweep"),
            _trade(4, "ADAUSDT", "short", -0.5, liquidity_context="location:near_resistance"),
        ],
    )

    result = analyze_post_bullish_sweep_counterfactual(data_path=data_path)

    assert result["current_metrics"]["trades"] == 4
    assert result["removed_bullish_sweep_metrics"]["trades"] == 2
    assert result["post_bullish_sweep_metrics"]["trades"] == 2
    assert "sweep:bullish_sweep" not in result["breakdowns"]["liquidity_context"]
    assert "sweep:bearish_sweep" in result["breakdowns"]["liquidity_context"]


def test_post_counterfactual_detects_system_profitability_after_removal(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -3.0, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", "long", -2.0, liquidity_sweep="bullish_sweep"),
            _trade(3, "SOLUSDT", "short", 1.5, liquidity_sweep="bearish_sweep"),
            _trade(4, "ADAUSDT", "short", 1.0),
        ],
    )

    result = analyze_post_bullish_sweep_counterfactual(data_path=data_path)

    assert result["current_metrics"]["total_r"] == -2.5
    assert result["post_bullish_sweep_metrics"]["total_r"] == 2.5
    assert result["answers"]["system_profitable_after_removal"] == "YES"


def test_post_counterfactual_ranks_new_enemy_after_bullish_sweep_removed(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, session="NEW_YORK", setup="MAIN_SIGNAL") for index in range(25)]
    rows.extend(_trade(index + 30, "SOLUSDT", "short", 1.0, session="LONDON", setup="MAIN_SIGNAL") for index in range(10))
    rows.append(_trade(99, "BTCUSDT", "long", -5.0, liquidity_sweep="bullish_sweep"))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_post_bullish_sweep_counterfactual(data_path=data_path)

    assert result["new_enemy_ranking"]
    assert result["new_enemy_ranking"][0]["dimension"] in {"symbol", "session", "setup_type", "long_subset"}
    assert result["new_enemy_ranking"][0]["classification"] == "CRITICAL"
    assert "Deep dive" in result["next_investigation_recommendation"]


def test_post_counterfactual_classifies_noise_watch_important_critical() -> None:
    assert classify_loss_component({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_loss_component({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_loss_component({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_loss_component({"trades": 20, "total_r": -5.0, "profit_factor": 0.8}) == "CRITICAL"


def test_post_counterfactual_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", "short", 1.0),
        ],
    )

    result = analyze_post_bullish_sweep_counterfactual(data_path=data_path)
    path = write_post_bullish_sweep_counterfactual_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "POST_BULLISH_SWEEP_COUNTERFACTUAL_ANALYSIS" in text
    assert "New Enemy Ranking" in text
    assert "Next Investigation Recommendation" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    setup: str = "MAIN_SIGNAL",
    score: float = 90,
    entry_context: str = "PULLBACK",
    liquidity_sweep: str = "",
    liquidity_context: str = "",
    reasons: str = "",
    warnings: str = "",
    penalties: str = "",
    trend_entry: str = "",
    trend_higher: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": entry_context,
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "liquidity_context": liquidity_context,
        "rejection_reasons": reasons,
        "warnings": warnings,
        "penalties": penalties,
        "trend_entry": trend_entry,
        "trend_higher": trend_higher,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
