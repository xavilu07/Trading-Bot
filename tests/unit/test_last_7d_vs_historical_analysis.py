from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.research.last_7d_vs_historical_analysis import (
    analyze_last_7d_vs_historical,
    audit_last_7d_data_sources,
    write_last_7d_data_source_audit,
    write_last_7d_vs_historical_report,
)


def test_last_7d_vs_historical_detects_recent_short_improvement(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    now = datetime(2026, 6, 5, 12, tzinfo=timezone.utc)
    rows = [
        *[_trade(index, "BTCUSDT", "short", "2026-06-0{}T12:00:00+00:00".format((index % 4) + 1), 1.5) for index in range(5)],
        *[_trade(index + 10, "BTCUSDT", "short", "2026-04-01T12:00:00+00:00", -1.0) for index in range(5)],
        *[_trade(index + 20, "ETHUSDT", "long", "2026-06-02T12:00:00+00:00", -1.0) for index in range(3)],
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_last_7d_vs_historical(data_path=data_path, now=now)

    assert result["periods"]["last_7d"]["metrics"]["total_trades"] == 8
    assert result["direction_comparison"]["short"]["classification"] == "IMPROVING"
    assert "outperforming" in result["direction_comparison"]["short"]["answer"]
    assert result["periods"]["last_7d"]["breakdowns"]["direction"]["short"]["total_r"] == 7.5


def test_last_7d_vs_historical_detects_recent_deterioration(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    now = datetime(2026, 6, 5, 12, tzinfo=timezone.utc)
    rows = [
        *[_trade(index, "SOLUSDT", "long", "2026-06-02T12:00:00+00:00", -1.0) for index in range(4)],
        *[_trade(index + 10, "SOLUSDT", "long", "2026-04-01T12:00:00+00:00", 1.5) for index in range(6)],
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_last_7d_vs_historical(data_path=data_path, now=now)

    assert result["direction_comparison"]["long"]["classification"] == "DETERIORATING"
    assert result["regime_shift_detection"]["classification"] == "DETERIORATING"
    assert result["executive_summary"]["recommended_action"] == "investigate further"


def test_last_7d_vs_historical_breakdowns_include_symbol_setup_regime_session_and_score_bucket(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    now = datetime(2026, 6, 5, 12, tzinfo=timezone.utc)
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "AVAXUSDT", "short", "2026-06-03T12:00:00+00:00", 1.5, score=92),
            _trade(2, "AVAXUSDT", "long", "2026-06-03T13:00:00+00:00", -1.0, score=72),
        ],
    )

    result = analyze_last_7d_vs_historical(data_path=data_path, now=now)
    breakdowns = result["periods"]["last_7d"]["breakdowns"]

    assert breakdowns["symbol"]["AVAXUSDT"]["total_trades"] == 2
    assert breakdowns["setup_type"]["MAIN_SIGNAL"]["total_trades"] == 2
    assert breakdowns["market_regime"]["TRENDING"]["total_trades"] == 2
    assert breakdowns["session"]["LONDON"]["total_trades"] == 2
    assert breakdowns["score_bucket"]["90+"]["total_trades"] == 1
    assert breakdowns["score_bucket"]["70-79"]["total_trades"] == 1


def test_last_7d_vs_historical_reads_large_canonical_dataset_and_respects_windows(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    now = datetime(2026, 6, 5, 12, tzinfo=timezone.utc)
    rows = [
        *[_trade(index, "BTCUSDT", "short", "2026-06-0{}T12:00:00+00:00".format((index % 4) + 1), 1.5) for index in range(7)],
        *[_trade(index + 10, "ETHUSDT", "long", "2026-05-20T12:00:00+00:00", -1.0) for index in range(5)],
        *[_trade(index + 20, "SOLUSDT", "long", "2026-04-01T12:00:00+00:00", 1.0) for index in range(3)],
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_last_7d_vs_historical(data_path=data_path, now=now)

    assert result["periods"]["full_history"]["metrics"]["total_trades"] == 15
    assert result["periods"]["last_30d"]["metrics"]["total_trades"] == 12
    assert result["periods"]["last_7d"]["metrics"]["total_trades"] == 7
    assert result["direction_comparison"]["short"]["metrics"]["last_7d"]["total_trades"] == 7


def test_last_7d_data_source_audit_explains_stale_canonical_source(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    now = datetime(2026, 6, 5, 12, tzinfo=timezone.utc)
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "short", "2026-05-18T12:00:00+00:00", 1.5)])
    _write_csv(reports_path / "outcome_intelligence.csv", [_trade(2, "ETHUSDT", "long", "2026-06-03T12:00:00+00:00", 1.5)])

    audit = audit_last_7d_data_sources(data_path=data_path, reports_path=reports_path, now=now)
    path = write_last_7d_data_source_audit(audit, reports_path)

    assert audit["canonical_closed_count"] == 1
    assert audit["canonical_last_7d_count"] == 0
    assert "older than the 7d window" in audit["why_last_7d_zero"]
    assert path.exists()
    assert "LAST_7D Data Source Audit" in path.read_text(encoding="utf-8")


def test_last_7d_vs_historical_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "short", "2026-06-03T12:00:00+00:00", 1.5)])

    result = analyze_last_7d_vs_historical(
        data_path=data_path,
        now=datetime(2026, 6, 5, 12, tzinfo=timezone.utc),
    )
    path = write_last_7d_vs_historical_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "LAST_7D_VS_HISTORICAL_REGIME_ANALYSIS" in text
    assert "REGIME SHIFT DETECTION" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    closed_at: str,
    result_r: float,
    *,
    score: float = 90,
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "PULLBACK",
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": closed_at,
        "closed_at": closed_at,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
