from __future__ import annotations

from pathlib import Path

from scripts.diagnostics_summary import build_summary, format_summary, load_rows


def test_diagnostics_summary_builds_expected_rankings_and_recommendations(tmp_path: Path) -> None:
    csv_path = tmp_path / "2026-04-24.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,scan_run_id,symbol,decision,setup_score,trend_entry_timeframe,trend_higher_timeframe,market_structure,liquidity_sweep,atr,rejection_reason",
                "2026-04-24T10:00:00+00:00,run_1,BTCUSDT,no_trade,45,bullish,bullish,range,none,1.2,quality_score_failed|market_structure_range|body_ratio_below_threshold",
                "2026-04-24T10:00:01+00:00,run_1,ETHUSDT,no_trade,40,bullish,bullish,range,none,1.1,quality_score_failed|market_structure_range",
                "2026-04-24T10:00:02+00:00,run_1,BTCUSDT,no_trade,35,bullish,bearish,range,none,1.0,quality_score_failed|distance_to_liquidity_failed",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_rows(csv_path)
    summary = build_summary(rows)
    rendered = format_summary(summary, csv_path)

    assert summary["total_symbols_analyzed"] == 3
    assert summary["total_no_trade"] == 3
    assert summary["rejection_reason_ranking"][0] == (
        "quality_score_failed|market_structure_range|body_ratio_below_threshold",
        1,
    )
    assert ("quality_score_failed", 3) in summary["filter_counts"]
    assert ("BTCUSDT", 2) in summary["blocked_symbols"]
    assert any("SETUP_SCORE_THRESHOLD" in item for item in summary["recommendations"])
    assert any("detector de estructura" in item for item in summary["recommendations"])
    assert "Total de NO_TRADE: 3" in rendered
    assert "BTCUSDT: 2" in rendered
