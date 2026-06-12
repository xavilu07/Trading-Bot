from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.secondary_failed_short_edge_tracker import (
    analyze_secondary_failed_short_edge_tracker,
    is_secondary_failed_short,
    recommend_profile,
    row_contains_reason,
    write_secondary_failed_short_edge_tracker_reports,
)


def test_detects_secondary_failed_short_in_any_field() -> None:
    row = _trade(1, "BTCUSDT", "short", 1.0, conditions_failed='["secondary_setup_requirements_failed"]')

    assert row_contains_reason(row)
    assert is_secondary_failed_short(row)
    assert not is_secondary_failed_short({**row, "direction": "long"})


def test_tracker_computes_base_and_profile_metrics(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "BTCUSDT", "short", 1.0, location="mid_range", session="LONDON", regime="RANGING")
        for index in range(6)
    ]
    rows.extend(
        _trade(index + 10, "ETHUSDT", "short", -1.0, location="near_support", session="ASIA", regime="TRENDING")
        for index in range(4)
    )
    rows.extend(
        _trade(index + 20, "SOLUSDT", "long", 1.0, location="mid_range", session="LONDON", regime="RANGING")
        for index in range(3)
    )
    rows.extend(
        _trade(index + 30, "BNBUSDT", "short", 1.0, location="mid_range", session="LONDON", regime="RANGING", conditions_failed="other_filter")
        for index in range(3)
    )
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_secondary_failed_short_edge_tracker(data_path=data_path)
    base = _profile(result, "BASE")
    profile_a = _profile(result, "PROFILE_A")
    profile_b = _profile(result, "PROFILE_B")

    assert base["metrics"]["trades"] == 10
    assert base["metrics"]["closed_trades"] == 10
    assert base["metrics"]["wins"] == 6
    assert base["metrics"]["losses"] == 4
    assert base["metrics"]["winrate"] == 60.0
    assert base["metrics"]["gross_win_r"] == 6.0
    assert base["metrics"]["gross_loss_r"] == 4.0
    assert base["metrics"]["profit_factor"] == 1.5
    assert base["metrics"]["total_r"] == 2.0
    assert profile_a["metrics"]["trades"] == 6
    assert profile_b["metrics"]["trades"] == 6
    assert profile_a["recommendation"] == "KEEP_SHADOW"


def test_profiles_c_and_d_are_evaluated(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "ADAUSDT", "short", 1.0, location="mid_range", session="ASIA", regime="HIGH_VOLATILITY")
        for index in range(5)
    ]
    rows.extend(
        _trade(index + 10, "XRPUSDT", "short", 1.0, location="mid_range", session="LONDON", regime="HIGH_VOLATILITY")
        for index in range(5)
    )
    rows.append(_trade(99, "BTCUSDT", "short", -1.0, location="mid_range", session="NEW_YORK", regime="RANGING"))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_secondary_failed_short_edge_tracker(data_path=data_path)

    assert _profile(result, "PROFILE_C")["metrics"]["trades"] == 5
    assert _profile(result, "PROFILE_C")["recommendation"] == "KEEP_SHADOW"
    assert _profile(result, "PROFILE_D")["metrics"]["trades"] == 10
    assert _profile(result, "PROFILE_D")["recommendation"] == "KEEP_SHADOW"


def test_recommendation_rules() -> None:
    assert recommend_profile({"trades": 20, "total_r": 5, "profit_factor": 1.5, "winrate": 50}) == "PROMOTE_TO_PRIORITY"
    assert recommend_profile({"trades": 5, "total_r": 1, "profit_factor": 1.1, "winrate": 40}) == "KEEP_SHADOW"
    assert recommend_profile({"trades": 10, "total_r": 0, "profit_factor": 0.9, "winrate": 30}) == "REJECT_PROFILE"
    assert recommend_profile({"trades": 4, "total_r": 1, "profit_factor": 2, "winrate": 100}) == "INSUFFICIENT_DATA"


def test_reports_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "short", 1.0)])

    result = analyze_secondary_failed_short_edge_tracker(data_path=data_path)
    paths = write_secondary_failed_short_edge_tracker_reports(result, reports_path)

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "SECONDARY_FAILED_SHORT_EDGE_TRACKER" in markdown
    assert "PROFILE_A" in markdown
    assert "SECONDARY_FAILED_SHORT_EDGE_TRACKER" in json_text


def _profile(result: dict[str, object], name: str) -> dict[str, object]:
    return next(row for row in result["profiles"] if row["profile"] == name)  # type: ignore[index,return-value]


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    location: str = "mid_range",
    session: str = "LONDON",
    regime: str = "RANGING",
    conditions_failed: str = "secondary_setup_requirements_failed",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": "SECONDARY_SIGNAL",
        "score": 75,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "conditions_failed": conditions_failed,
        "entry_or_rejection_reason": "",
        "penalties": "",
        "avoidance_warnings": "",
        "session": session,
        "market_regime": regime,
        "trade_location": location,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
