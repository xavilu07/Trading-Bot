from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.directional_confluence_failed_deep_dive import (
    analyze_directional_confluence_failed_deep_dive,
    classify_loss_component,
    write_directional_confluence_failed_deep_dive_report,
)


def test_directional_confluence_filters_target_token_across_fields(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, warnings="directional_confluence_failed"),
            _trade(2, "ETHUSDT", "long", -1.0, penalties="directional_confluence_failed"),
            _trade(3, "SOLUSDT", "short", -1.0, reasons="directional_confluence_failed"),
            _trade(4, "XRPUSDT", "short", 1.0, warnings="against_htf"),
        ],
    )

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)

    assert result["metrics"]["trades"] == 3
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "ETHUSDT" in result["breakdowns"]["symbol"]
    assert "SOLUSDT" in result["breakdowns"]["symbol"]
    assert "XRPUSDT" not in result["breakdowns"]["symbol"]


def test_directional_confluence_detects_toxic_subgroups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "XRPUSDT", "long", -1.0, warnings="directional_confluence_failed", session="NEW_YORK")
        for index in range(30)
    ]
    rows.extend(_trade(index + 40, "SOLUSDT", "short", 1.0, session="LONDON") for index in range(30))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)

    assert result["classification"] == "CRITICAL"
    assert result["toxic_subgroups"]
    assert result["answers"]["globally_toxic"] == "YES"
    assert result["recommended_action"] in {"FULL_BLOCK", "SHADOW_BLOCK", "PARTIAL_BLOCK"}


def test_directional_confluence_finds_survivor_subset(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "SOLUSDT", "short", 1.0, warnings="directional_confluence_failed", session="LONDON")
        for index in range(5)
    ]
    rows.extend(
        _trade(index + 20, "BTCUSDT", "long", -1.0, warnings="directional_confluence_failed", session="NEW_YORK")
        for index in range(3)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)

    assert result["survivors"]
    assert result["survivors"][0]["metrics"]["trades"] >= 5
    assert result["answers"]["survivor_subgroup"] != "none"


def test_directional_confluence_counterfactual_removal_improves_pf_and_tracks_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, warnings="directional_confluence_failed") for index in range(5)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0) for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)
    counterfactual = result["counterfactual_removal"]

    assert counterfactual["trades_removed"] == 5
    assert counterfactual["current_metrics"]["profit_factor"] == 1.0
    assert counterfactual["without_directional_confluence_metrics"]["profit_factor"] == "inf"
    assert counterfactual["winrate_delta"] == 50.0


def test_directional_confluence_impact_ranking_identifies_biggest_removal(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, warnings="directional_confluence_failed", session="NEW_YORK") for index in range(5)]
    rows.extend(
        _trade(index + 20, "SOLUSDT", "short", 1.0, warnings="directional_confluence_failed", session="LONDON")
        for index in range(3)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)

    assert result["impact_ranking"]
    assert result["impact_ranking"][0]["r_improvement"] > 0


def test_directional_confluence_classifies_components() -> None:
    assert classify_loss_component({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_loss_component({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_loss_component({"trades": 5, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_loss_component({"trades": 30, "total_r": -5.0, "profit_factor": 0.8}) == "CRITICAL"


def test_directional_confluence_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [_trade(1, "BTCUSDT", "long", -1.0, warnings="directional_confluence_failed")],
    )

    result = analyze_directional_confluence_failed_deep_dive(data_path=data_path)
    path = write_directional_confluence_failed_deep_dive_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "DIRECTIONAL_CONFLUENCE_FAILED_DEEP_DIVE" in text
    assert "Counterfactual Removal" in text
    assert "Impact Ranking" in text
    assert "Recommended Action" in text


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
