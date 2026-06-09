from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.elite_shadow_mode_simulation import (
    analyze_elite_shadow_mode_simulation,
    classify_elite_profile,
    write_elite_shadow_mode_simulation_reports,
)


def test_excludes_existing_production_blocks_from_baseline(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "long", -1.0, warnings="against_htf", entry_context="BREAKOUT") for index in range(5))
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, score=95, trend_higher="bearish") for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_shadow_mode_simulation(data_path=data_path)

    assert result["baseline_after_production_blocks"]["trades"] == 10
    assert result["excluded_metrics"]["trades"] == 10
    assert _profile(result, "PROFILE_A")["metrics"]["trades"] == 10


def test_profiles_progressively_filter_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.0, score=95, trend_higher="bearish") for index in range(20)]
    rows.extend(_trade(index + 30, "ETHUSDT", "short", 1.0, score=95, trend_higher="bearish", setup="SECONDARY_SIGNAL") for index in range(15))
    rows.extend(
        _trade(index + 60, "AAVEUSDT", "short", 1.0, score=95, trend_higher="bearish", setup="SECONDARY_SIGNAL", liquidity_sweep="bearish_sweep")
        for index in range(12)
    )
    rows.extend(_trade(index + 90, "XRPUSDT", "short", -1.0, score=85, trend_higher="bearish") for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_shadow_mode_simulation(data_path=data_path)

    assert _profile(result, "PROFILE_A")["metrics"]["trades"] == 47
    assert _profile(result, "PROFILE_B")["metrics"]["trades"] == 47
    assert _profile(result, "PROFILE_C")["metrics"]["trades"] == 27
    assert _profile(result, "PROFILE_D")["metrics"]["trades"] == 12
    assert _profile(result, "PROFILE_A")["trade_reduction_pct"] < _profile(result, "PROFILE_D")["trade_reduction_pct"]


def test_london_and_high_volatility_profiles_are_evaluated_separately(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(
            index,
            "SOLUSDT",
            "short",
            1.5,
            score=95,
            trend_higher="bearish",
            setup="SECONDARY_SIGNAL",
            liquidity_sweep="bearish_sweep",
            session="LONDON",
        )
        for index in range(10)
    ]
    rows.extend(
        _trade(
            index + 20,
            "ETHUSDT",
            "short",
            0.5,
            score=95,
            trend_higher="bearish",
            setup="SECONDARY_SIGNAL",
            liquidity_sweep="bearish_sweep",
            session="OVERLAP",
            regime="HIGH_VOLATILITY",
        )
        for index in range(10)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_shadow_mode_simulation(data_path=data_path)

    assert _profile(result, "PROFILE_E")["metrics"]["trades"] == 10
    assert _profile(result, "PROFILE_F")["metrics"]["trades"] == 10
    assert _profile(result, "PROFILE_E")["metrics"]["total_r"] > _profile(result, "PROFILE_F")["metrics"]["total_r"]


def test_profile_answers_identify_max_pf_and_recommend_shadow(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(
            index,
            "SOLUSDT",
            "short",
            2.0,
            score=95,
            trend_higher="bearish",
            setup="SECONDARY_SIGNAL",
            liquidity_sweep="bearish_sweep",
            session="LONDON",
        )
        for index in range(10)
    ]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, score=90, trend_higher="bullish") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_shadow_mode_simulation(data_path=data_path)

    assert "PROFILE_E" in result["answers"]["max_pf_profile"]
    assert result["answers"]["worth_shadow_testing"] == "YES"
    assert result["recommended_action"] in {"ELITE_MODE_READY", "SHADOW_TEST_PROFILE_E", "BUILD_ELITE_FILTER"}


def test_classification_helper() -> None:
    assert classify_elite_profile({"trades": 4, "total_r": 10, "profit_factor": 3}) == "NO_EDGE"
    assert classify_elite_profile({"trades": 10, "total_r": -1, "profit_factor": 2}) == "NO_EDGE"
    assert classify_elite_profile({"trades": 10, "total_r": 2, "profit_factor": 1.21}) == "PROMISING"
    assert classify_elite_profile({"trades": 10, "total_r": 2, "profit_factor": 1.41}) == "STRONG"
    assert classify_elite_profile({"trades": 10, "total_r": 2, "profit_factor": 1.81}) == "ELITE"


def test_report_markdown_and_json_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "SOLUSDT", "short", 1.0, score=95, trend_higher="bearish")])

    result = analyze_elite_shadow_mode_simulation(data_path=data_path)
    paths = write_elite_shadow_mode_simulation_reports(result, tmp_path / "reports")

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "ELITE_SHADOW_MODE_SIMULATION" in markdown
    assert "Profile Simulation" in markdown
    assert "ELITE_SHADOW_MODE_SIMULATION" in json_text


def _profile(result: dict[str, object], name: str) -> dict[str, object]:
    return next(row for row in result["profiles"] if row["profile"] == name)  # type: ignore[index,return-value]


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
    warnings: str = "",
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
        "trade_location": "premium_zone",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "warnings": warnings,
        "trend_higher": trend_higher,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
