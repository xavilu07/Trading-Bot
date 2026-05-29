from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.context_toxicity_deep_dive import (
    analyze_context_toxicity,
    load_context_toxicity_records,
    write_context_toxicity_reports,
)


def test_high_volatility_long_negative_is_confirmed_toxic() -> None:
    records = [_row(result_r=-1.0, direction="long", market_regime="HIGH_VOLATILITY") for _ in range(5)]

    result = analyze_context_toxicity(records, min_trades=5)

    assert any(row["segment"] == "HIGH_VOLATILITY_LONG" for row in result["confirmed_toxic_contexts"])
    assert any("HIGH_VOLATILITY_LONG" in item for item in result["recommended_keep_blocked"])


def test_high_volatility_short_london_high_volume_is_hidden_edge() -> None:
    records = [
        _row(result_r=1.0, direction="short", market_regime="HIGH_VOLATILITY", session="LONDON", volume_ratio=1.4)
        for _ in range(5)
    ]

    result = analyze_context_toxicity(records, min_trades=5)

    assert any(row["segment"] == "HIGH_VOLATILITY_SHORT" for row in result["hidden_edge_contexts"])
    assert result["recommended_candidate_relaxations"][0] != "no_candidate_relaxation_detected"


def test_choppy_range_short_london_high_volume_is_hidden_edge_not_global_relaxation() -> None:
    records = [
        _row(result_r=1.0, direction="short", entry_context="CHOPPY_RANGE", session="LONDON", volume_ratio=1.5)
        for _ in range(5)
    ]

    result = analyze_context_toxicity(records, min_trades=5)

    assert any(row["segment"] == "CHOPPY_RANGE_SHORT" for row in result["hidden_edge_contexts"])
    assert "do_not_relax_choppy_range_or_high_volatility_without_direction_session_volume_filters" in result["what_not_to_change"]


def test_unknown_contexts_are_reported_as_unstable_with_low_sample() -> None:
    records = [_row(result_r=1.0, setup_type="UNKNOWN", session="UNKNOWN", trade_location="UNKNOWN")]

    result = analyze_context_toxicity(records, min_trades=5)

    assert result["unstable_contexts"]
    assert any(row["target_context"] == "setup_type=UNKNOWN" for row in result["unstable_contexts"])


def test_context_toxicity_loads_and_writes_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [_row(result_r=-1.0, direction="long", market_regime="HIGH_VOLATILITY")],
    )

    records = load_context_toxicity_records(data_path, reports_path)
    result = analyze_context_toxicity(records, min_trades=1)
    paths = write_context_toxicity_reports(result, reports_path)

    assert len(records) == 1
    assert paths["json_path"].exists()
    assert paths["csv_path"].exists()
    assert paths["summary_path"].exists()


def _row(
    *,
    result_r: float,
    direction: str = "long",
    session: str = "LONDON",
    setup_type: str = "MAIN_SIGNAL",
    entry_context: str = "BREAKOUT",
    market_regime: str = "TRENDING",
    trade_location: str = "mid_range",
    volume_ratio: float = 1.0,
) -> dict[str, object]:
    return {
        "symbol": "TESTUSDT",
        "direction": direction,
        "session": session,
        "setup_type": setup_type,
        "entry_context": entry_context,
        "market_regime": market_regime,
        "trade_location": trade_location,
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "score": 80,
        "volume_ratio": volume_ratio,
        "body_ratio": 0.55,
        "risk_reward": 2.0,
        "trend_entry": "bearish" if direction == "short" else "bullish",
        "trend_higher": "bearish" if direction == "short" else "bullish",
        "opened_at": "2026-01-01T10:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
