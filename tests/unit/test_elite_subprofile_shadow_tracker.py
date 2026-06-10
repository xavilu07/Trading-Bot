from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.elite_subprofile_shadow_tracker import (
    analyze_elite_subprofile_shadow_tracker,
    matches_profile_g,
    matches_profile_h,
    recommend_subprofile,
    write_elite_subprofile_shadow_tracker_reports,
)


def test_profile_g_and_h_match_logic() -> None:
    profile_g = _trade(
        1,
        "BTCUSDT",
        "long",
        1.0,
        setup="SECONDARY_SIGNAL",
        score=95,
        trend_higher="bullish",
        session="OVERLAP",
        regime="HIGH_VOLATILITY",
        location="near_resistance",
    )
    assert matches_profile_g(profile_g)
    assert matches_profile_h(profile_g)
    assert not matches_profile_g({**profile_g, "trade_location": "mid_range"})
    assert not matches_profile_h({**profile_g, "market_regime": "TRENDING"})
    assert not matches_profile_g({**profile_g, "setup_type": "MAIN_SIGNAL"})
    assert not matches_profile_h({**profile_g, "score": 89})


def test_subprofile_tracker_computes_profile_metrics_and_deltas(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "BTCUSDT", "long", 2.0, session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance", trend_higher="bullish")
        for index in range(6)
    ]
    rows.extend(
        _trade(index + 10, "ETHUSDT", "long", -1.0, session="LONDON", regime="HIGH_VOLATILITY", location="near_support", trend_higher="bullish")
        for index in range(4)
    )
    rows.extend(
        _trade(index + 20, "SOLUSDT", "short", 1.0, session="LONDON", regime="TRENDING", location="premium_zone", trend_higher="bearish")
        for index in range(5)
    )
    rows.extend(
        _trade(index + 30, "BNBUSDT", "long", 1.0, setup="MAIN_SIGNAL", session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance", trend_higher="bullish")
        for index in range(3)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_subprofile_shadow_tracker(data_path=data_path)
    profile_g = _profile(result, "PROFILE_G")
    profile_h = _profile(result, "PROFILE_H")

    assert result["elite_profile_c_baseline"]["trades"] == 15
    assert profile_g["tracked"] == 6
    assert profile_g["metrics"]["total_r"] == 12.0
    assert profile_h["tracked"] == 10
    assert profile_h["metrics"]["total_r"] == 8.0
    assert profile_g["deltas_vs_elite_c"]["pf_delta"] > 0
    assert profile_h["by_symbol"]["BTCUSDT"]["tracked"] == 6
    assert profile_h["by_session"]["OVERLAP"]["tracked"] == 6
    assert profile_h["by_regime"]["HIGH_VOLATILITY"]["tracked"] == 10


def test_recommendation_logic() -> None:
    assert recommend_subprofile({"trades": 20, "total_r": 10, "profit_factor": 2.1, "winrate": 60}) == "PROMOTE_TO_PRIORITY"
    assert recommend_subprofile({"trades": 10, "total_r": -1, "profit_factor": 0.9, "winrate": 40}) == "REJECT_PROFILE"
    assert recommend_subprofile({"trades": 6, "total_r": 10, "profit_factor": 3.0, "winrate": 80}) == "KEEP_SHADOW"


def test_reports_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    rows = [
        _trade(index, "BTCUSDT", "long", 1.0, session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance", trend_higher="bullish")
        for index in range(5)
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_subprofile_shadow_tracker(data_path=data_path)
    paths = write_elite_subprofile_shadow_tracker_reports(result, reports_path)

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "ELITE_SUBPROFILE_SHADOW_TRACKER" in markdown
    assert "PROFILE_G" in markdown
    assert "PROFILE_H" in json_text


def _profile(result: dict[str, object], name: str) -> dict[str, object]:
    return next(row for row in result["profiles"] if row["profile"] == name)  # type: ignore[index,return-value]


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    setup: str = "SECONDARY_SIGNAL",
    score: float = 95,
    trend_higher: str = "bullish",
    session: str = "OVERLAP",
    regime: str = "HIGH_VOLATILITY",
    location: str = "near_resistance",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "score": score,
        "trend_higher": trend_higher,
        "session": session,
        "market_regime": regime,
        "trade_location": location,
        "entry_context": "BREAKOUT",
        "liquidity_sweep": "none",
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
