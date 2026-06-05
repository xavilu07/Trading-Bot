from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.score_80_89_deep_dive import (
    analyze_score_80_89_deep_dive,
    classify_loss_component,
    write_score_80_89_deep_dive_report,
)


def test_score_80_89_filters_bucket_and_excludes_bullish_sweep(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, score=85),
            _trade(2, "ETHUSDT", "long", 1.0, score=79),
            _trade(3, "SOLUSDT", "short", 1.0, score=90),
            _trade(4, "ADAUSDT", "long", -1.0, score=88, liquidity_sweep="bullish_sweep"),
            _trade(5, "XRPUSDT", "short", 1.5, score=82, liquidity_sweep="bearish_sweep"),
        ],
    )

    result = analyze_score_80_89_deep_dive(data_path=data_path)

    assert result["metrics"]["trades"] == 2
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "XRPUSDT" in result["breakdowns"]["symbol"]
    assert "ADAUSDT" not in result["breakdowns"]["symbol"]
    assert "sweep:bullish_sweep" not in result["breakdowns"]["liquidity_context"]


def test_score_80_89_ranks_toxic_subgroups_and_recommends_partial_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, score=85, session="NEW_YORK") for index in range(20)]
    rows.extend(_trade(index + 30, "SOLUSDT", "short", 1.0, score=85, session="LONDON") for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_deep_dive(data_path=data_path)

    assert result["classification"] == "CRITICAL"
    assert result["toxic_subgroups"]
    assert result["toxic_subgroups"][0]["classification"] == "CRITICAL"
    assert result["answers"]["recommended_action"] == "PARTIAL_BLOCK"
    assert any(token in result["answers"]["main_loss_subgroup"] for token in ("session=NEW_YORK", "symbol=XRPUSDT"))


def test_score_80_89_finds_survivor_with_minimum_sample(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.0, score=85, session="LONDON", setup="MAIN_SIGNAL") for index in range(10)]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, score=85, session="NEW_YORK", setup="SECONDARY_SIGNAL") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_deep_dive(data_path=data_path)

    assert result["survivors_inside_80_89"]
    assert result["survivors_inside_80_89"][0]["metrics"]["trades"] >= 10
    assert "SOLUSDT" in result["answers"]["safe_survivor"] or "session=LONDON" in result["answers"]["safe_survivor"]


def test_score_80_89_counterfactual_removes_worst_group_and_improves_pf(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, score=85, session="NEW_YORK") for index in range(12)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, score=85, session="LONDON") for index in range(12))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_deep_dive(data_path=data_path)
    counterfactual = result["top_subgroup_counterfactual"]

    assert counterfactual["removed_group"] != "none"
    assert counterfactual["remaining_metrics"]["profit_factor"] == "inf"
    assert counterfactual["remaining_metrics"]["total_r"] > result["metrics"]["total_r"]


def test_score_80_89_classifies_components() -> None:
    assert classify_loss_component({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_loss_component({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_loss_component({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_loss_component({"trades": 20, "total_r": -5.0, "profit_factor": 0.8}) == "CRITICAL"


def test_score_80_89_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", -1.0, score=85)])

    result = analyze_score_80_89_deep_dive(data_path=data_path)
    path = write_score_80_89_deep_dive_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "SCORE_80_89_DEEP_DIVE" in text
    assert "Toxic Subgroups" in text
    assert "Counterfactual Recommendation" in text


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
