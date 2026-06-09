from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.distance_to_liquidity_root_cause_analysis import (
    analyze_distance_to_liquidity_root_cause,
    classify_combination,
    classify_distance_to_liquidity_component,
    write_distance_to_liquidity_root_cause_reports,
)


def test_distance_penalty_filters_target_across_fields(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, penalties="distance_to_liquidity_penalty"),
            _trade(2, "ETHUSDT", "short", -1.0, reasons="distance_to_liquidity_penalty"),
            _trade(3, "SOLUSDT", "long", -1.0, conditions_failed="distance_to_liquidity_penalty"),
            _trade(4, "XRPUSDT", "short", 1.0, penalties="against_htf"),
        ],
    )

    result = analyze_distance_to_liquidity_root_cause(data_path=data_path)

    assert result["distance_to_liquidity_penalty_metrics"]["trades"] == 3
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "ETHUSDT" in result["breakdowns"]["symbol"]
    assert "SOLUSDT" in result["breakdowns"]["symbol"]
    assert "XRPUSDT" not in result["breakdowns"]["symbol"]


def test_detects_toxic_distance_component_and_combinations(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "XRPUSDT", "long", -1.0, setup="MAIN_SIGNAL", penalties="distance_to_liquidity_penalty")
        for index in range(30)
    ]
    rows.extend(_trade(index + 40, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL") for index in range(30))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_distance_to_liquidity_root_cause(data_path=data_path)
    names = {row["name"] for row in result["toxic_combinations"]}

    assert result["classification"] == "CRITICAL"
    assert result["answers"]["liquidity_distance_itself_toxic"] == "YES"
    assert "distance_to_liquidity_penalty + MAIN_SIGNAL" in names
    assert "distance_to_liquidity_penalty + LONG" in names
    assert result["recommended_action"] in {"PARTIAL_BLOCK", "FULL_BLOCK", "REDEFINE_ENTRY", "SHADOW_BLOCK"}


def test_counterfactual_after_existing_blocks_separates_correlation(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "BTCUSDT", "long", -1.0, penalties="distance_to_liquidity_penalty", liquidity_sweep="bullish_sweep")
        for index in range(10)
    ]
    rows.extend(
        _trade(index + 20, "ETHUSDT", "long", -1.0, penalties="distance_to_liquidity_penalty", warnings="against_htf", entry_context="BREAKOUT")
        for index in range(10)
    )
    rows.extend(_trade(index + 40, "SOLUSDT", "short", 1.0) for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_distance_to_liquidity_root_cause(data_path=data_path)
    post_blocks = result["counterfactuals"]["without_distance_to_liquidity_penalty_after_existing_blocks"]

    assert result["distance_to_liquidity_penalty_metrics"]["trades"] == 20
    assert result["distance_to_liquidity_penalty_after_existing_blocks_metrics"]["trades"] == 0
    assert post_blocks["removed_trades"] == 0
    assert result["answers"]["root_cause_or_correlated"] == "correlated_with_existing_blocked_contexts"


def test_finds_survivor_subset(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "SOLUSDT", "short", 1.0, session="LONDON", penalties="distance_to_liquidity_penalty")
        for index in range(10)
    ]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, session="NEW_YORK", penalties="distance_to_liquidity_penalty") for index in range(4))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_distance_to_liquidity_root_cause(data_path=data_path)

    assert result["survivors"]
    assert result["survivors"][0]["metrics"]["trades"] >= 10
    assert result["answers"]["best_survivor"] != "none"


def test_classification_helpers() -> None:
    assert classify_distance_to_liquidity_component({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_distance_to_liquidity_component({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_distance_to_liquidity_component({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_distance_to_liquidity_component({"trades": 30, "total_r": -5.0, "profit_factor": 0.8}) == "CRITICAL"
    assert classify_combination(
        {
            "removed_trades": 30,
            "r_improvement": 5,
            "pf_improvement": 0.1,
            "profitable_trades_lost": 5,
            "losing_trades_removed": 20,
            "removed_metrics": {"profit_factor": 0.5},
        }
    ) == "CRITICAL"


def test_report_markdown_and_json_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", -1.0, penalties="distance_to_liquidity_penalty")])

    result = analyze_distance_to_liquidity_root_cause(data_path=data_path)
    paths = write_distance_to_liquidity_root_cause_reports(result, tmp_path / "reports")

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS" in markdown
    assert "Counterfactuals" in markdown
    assert "DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS" in json_text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    setup: str = "MAIN_SIGNAL",
    score: float = 85,
    entry_context: str = "PULLBACK",
    trade_location: str = "mid_range",
    liquidity_sweep: str = "",
    liquidity_context: str = "",
    reasons: str = "",
    warnings: str = "",
    penalties: str = "",
    failed_filters: str = "",
    conditions_failed: str = "",
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
        "trade_location": trade_location,
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
        "failed_filters": failed_filters,
        "conditions_failed": conditions_failed,
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
