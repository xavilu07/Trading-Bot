from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.main_signal_long_root_cause_analysis import (
    analyze_main_signal_long_root_cause,
    classify_main_signal_long_root_cause,
    classify_root_cause,
    write_main_signal_long_root_cause_reports,
)


def test_filters_main_signal_long_and_builds_comparisons(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0),
            _trade(2, "ETHUSDT", "short", "MAIN_SIGNAL", 1.2),
            _trade(3, "SOLUSDT", "long", "SECONDARY_SIGNAL", 1.1),
            _trade(4, "ADAUSDT", "short", "SECONDARY_SIGNAL", -1.0),
        ],
    )

    result = analyze_main_signal_long_root_cause(data_path=data_path)

    assert result["main_signal_long_baseline"]["trades"] == 1
    assert result["comparisons"]["MAIN_SIGNAL_SHORT"]["metrics"]["trades"] == 1
    assert result["comparisons"]["SECONDARY_SIGNAL_LONG"]["metrics"]["trades"] == 1
    assert result["comparisons"]["NON_MAIN_SIGNAL_LONG"]["metrics"]["trades"] == 3
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "ETHUSDT" not in result["breakdowns"]["symbol"]


def test_existing_production_block_overlap_is_measured(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, liquidity_sweep="bullish_sweep")
        for index in range(10)
    ]
    rows.extend(
        _trade(index + 20, "ETHUSDT", "long", "MAIN_SIGNAL", -1.0, warnings="against_htf", entry_context="BREAKOUT")
        for index in range(10)
    )
    rows.extend(_trade(index + 40, "SOLUSDT", "long", "MAIN_SIGNAL", 1.0, session="LONDON") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_root_cause(data_path=data_path)
    overlap = result["existing_production_blocks"]

    assert overlap["covered_metrics"]["trades"] == 20
    assert overlap["remaining_after_existing_blocks"]["trades"] == 5
    assert result["counterfactuals"]["without_existing_production_blocks"]["removed_trades"] == 20
    assert "bullish_sweep" in overlap["rules"]
    assert "against_htf + BREAKOUT" in overlap["rules"]


def test_detects_non_overlapping_toxic_root_cause(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "XRPUSDT", "long", "MAIN_SIGNAL", -1.0, penalties="distance_to_liquidity_penalty")
        for index in range(12)
    ]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", "MAIN_SIGNAL", 1.0) for index in range(20))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_root_cause(data_path=data_path)
    names = {row["name"] for row in result["toxic_root_causes"]}

    assert "MAIN_SIGNAL LONG + distance_to_liquidity_penalty" in names
    assert "distance_to_liquidity_penalty" in result["answers"]["next_best_non_overlapping_root_cause"]
    assert result["answers"]["still_toxic_after_existing_blocks"] == "YES"


def test_survivor_and_tiny_promising_detection(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "long", "MAIN_SIGNAL", 1.0, session="LONDON") for index in range(10)]
    rows.extend(_trade(index + 20, "AAVEUSDT", "long", "MAIN_SIGNAL", 1.0, session="OVERLAP", regime="RANGING") for index in range(6))
    rows.extend(_trade(index + 40, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="HIGH_VOLATILITY") for index in range(12))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_root_cause(data_path=data_path)

    assert result["survivor_longs"]
    assert result["tiny_promising_longs"]
    assert result["answers"]["best_survivor"] != "none"
    assert result["recommended_action"] in {"KEEP", "REDEFINE_MAIN_SIGNAL_LONG", "PARTIAL_BLOCK", "SHADOW_BLOCK"}


def test_counterfactuals_include_required_scenarios(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, liquidity_sweep="bullish_sweep") for index in range(10)]
    rows.extend(
        _trade(index + 20, "ETHUSDT", "long", "MAIN_SIGNAL", -1.0, warnings="against_htf", entry_context="BREAKOUT")
        for index in range(10)
    )
    rows.extend(_trade(index + 40, "XRPUSDT", "long", "MAIN_SIGNAL", -1.0, penalties="body_ratio_below_threshold") for index in range(10))
    rows.extend(_trade(index + 60, "SOLUSDT", "short", "MAIN_SIGNAL", 1.0) for index in range(30))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_root_cause(data_path=data_path)
    counterfactuals = result["counterfactuals"]

    assert counterfactuals["without_all_main_signal_long"]["removed_trades"] == 30
    assert counterfactuals["without_bullish_sweep_already_blocked_contexts"]["removed_trades"] == 10
    assert counterfactuals["without_against_htf_breakout_already_blocked_contexts"]["removed_trades"] == 10
    assert counterfactuals["without_remaining_toxic_main_signal_long_after_existing_blocks"]["removed_trades"] == 10
    assert counterfactuals["without_worst_single_root_cause"]["name"] != "none"


def test_classification_helpers() -> None:
    assert classify_main_signal_long_root_cause({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_main_signal_long_root_cause({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_main_signal_long_root_cause({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_main_signal_long_root_cause({"trades": 30, "total_r": -10.0, "profit_factor": 0.8}) == "CRITICAL"
    assert classify_root_cause(
        {
            "removed_trades": 30,
            "r_improvement": 10,
            "pf_improvement": 0.2,
            "profitable_trades_lost": 5,
            "losing_trades_removed": 20,
            "removed_metrics": {"profit_factor": 0.5},
        }
    ) == "CRITICAL"


def test_report_markdown_and_json_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", 1.5)])

    result = analyze_main_signal_long_root_cause(data_path=data_path)
    paths = write_main_signal_long_root_cause_reports(result, tmp_path / "reports")

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS" in markdown
    assert "Toxic Root Causes" in markdown
    assert "MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS" in json_text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    setup: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    score: float = 90,
    entry_context: str = "PULLBACK",
    trade_location: str = "mid_range",
    reasons: str = "",
    warnings: str = "",
    penalties: str = "",
    failed_filters: str = "",
    conditions_failed: str = "",
    liquidity_sweep: str = "",
    trend_entry: str = "",
    trend_higher: str = "",
    volume_ratio: float = 1.3,
    body_ratio: float = 0.6,
    distance_to_liquidity_atr: float = 1.1,
    risk_reward: float = 2.0,
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": entry_context,
        "trade_location": trade_location,
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "rejection_reasons": reasons,
        "warnings": warnings,
        "penalties": penalties,
        "failed_filters": failed_filters,
        "conditions_failed": conditions_failed,
        "liquidity_sweep": liquidity_sweep,
        "trend_entry": trend_entry,
        "trend_higher": trend_higher,
        "volume_ratio": volume_ratio,
        "body_ratio": body_ratio,
        "distance_to_liquidity_atr": distance_to_liquidity_atr,
        "risk_reward": risk_reward,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
