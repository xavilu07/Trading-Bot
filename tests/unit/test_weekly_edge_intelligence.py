from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.research.weekly_edge_intelligence import (
    analyze_weekly_edge_intelligence,
    generate_weekly_edge_intelligence,
    write_weekly_edge_intelligence_reports,
)


def test_weekly_edge_intelligence_collects_required_profiles(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(1, "BTCUSDT", "long", 2.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish", session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance"),
        _trade(2, "ETHUSDT", "long", -1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish", session="LONDON", regime="HIGH_VOLATILITY", location="mid_range"),
        _trade(3, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bearish", session="LONDON", regime="TRENDING", location="premium_zone"),
        _trade(4, "XRPUSDT", "short", 1.5, setup="SECONDARY_SIGNAL", score=75, location="mid_range", entry_context="BREAKOUT", conditions_failed="secondary_setup_requirements_failed"),
        _trade(5, "ADAUSDT", "short", -1.0, setup="SECONDARY_SIGNAL", score=75, location="mid_range", entry_context="PULLBACK", conditions_failed="secondary_setup_requirements_failed"),
        _trade(6, "BNBUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=75, location="near_support", entry_context="BREAKOUT", conditions_failed="secondary_setup_requirements_failed"),
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_weekly_edge_intelligence(
        data_path=data_path,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )

    assert [profile["profile"] for profile in result["profiles"]] == [
        "Elite Profile C",
        "Profile G",
        "Profile H",
        "Secondary Failed Profile A",
        "Secondary Failed Profile E",
    ]
    assert _profile(result, "Elite Profile C")["metrics"]["trades"] == 3
    assert _profile(result, "Profile G")["metrics"]["trades"] == 1
    assert _profile(result, "Profile H")["metrics"]["trades"] == 2
    assert _profile(result, "Secondary Failed Profile A")["metrics"]["trades"] == 2
    assert _profile(result, "Secondary Failed Profile E")["metrics"]["trades"] == 1


def test_weekly_edge_intelligence_counts_new_trades_last_7d(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(1, "BTCUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish", opened_at="2026-06-14T10:00:00+00:00"),
        _trade(2, "ETHUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish", opened_at="2026-06-01T10:00:00+00:00"),
        _trade(3, "DOGEUSDT", "short", 1.0, location="mid_range", entry_context="BREAKOUT", conditions_failed="secondary_setup_requirements_failed", opened_at="2026-06-13T10:00:00+00:00"),
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_weekly_edge_intelligence(
        data_path=data_path,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )

    assert _profile(result, "Elite Profile C")["new_trades_last_7d"] == 1
    assert _profile(result, "Secondary Failed Profile A")["new_trades_last_7d"] == 1
    assert _profile(result, "Secondary Failed Profile E")["new_trades_last_7d"] == 1


def test_weekly_edge_intelligence_summary_groups_recommendations(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "DOGEUSDT", "short", 1.0, location="mid_range", entry_context="BREAKOUT", conditions_failed="secondary_setup_requirements_failed")
        for index in range(1, 22)
    ]
    rows.extend(
        _trade(index + 100, "BTCUSDT", "long", -1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish", session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance")
        for index in range(10)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_weekly_edge_intelligence(
        data_path=data_path,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )

    assert "Secondary Failed Profile A" in result["summary"]["PROMOTE_TO_PRIORITY"]
    assert "Secondary Failed Profile E" in result["summary"]["PROMOTE_TO_PRIORITY"]
    assert "Elite Profile C" in result["summary"]["REJECT_PROFILE"]
    assert "Profile G" in result["summary"]["REJECT_PROFILE"]
    assert "Profile H" in result["summary"]["REJECT_PROFILE"]


def test_weekly_edge_intelligence_reports_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=95, trend_higher="bullish")])

    result = analyze_weekly_edge_intelligence(data_path=data_path)
    paths = write_weekly_edge_intelligence_reports(result, reports_path)

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "Weekly Edge Intelligence" in markdown
    assert "Elite Profile C" in markdown
    assert "WEEKLY_EDGE_INTELLIGENCE" in json_text


def test_generate_weekly_edge_intelligence_returns_report_paths(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [])

    result = generate_weekly_edge_intelligence(data_path=data_path, reports_path=reports_path)

    assert Path(result["markdown_path"]).exists()
    assert Path(result["json_path"]).exists()


def _profile(result: dict[str, object], name: str) -> dict[str, object]:
    return next(profile for profile in result["profiles"] if profile["profile"] == name)  # type: ignore[index,return-value]


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    setup: str = "SECONDARY_SIGNAL",
    score: float = 75,
    trend_higher: str = "bearish",
    session: str = "LONDON",
    regime: str = "RANGING",
    location: str = "mid_range",
    entry_context: str = "BREAKOUT",
    conditions_failed: str = "",
    opened_at: str = "2026-06-14T12:00:00+00:00",
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
        "entry_context": entry_context,
        "conditions_failed": conditions_failed,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": opened_at,
        "closed_at": "2026-06-14T13:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["trade_id", "status", "result_r"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
