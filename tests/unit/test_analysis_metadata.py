from __future__ import annotations

from trading_signals.app.settings import Settings
from trading_signals.application.use_cases.analyze_symbol import _detect_break_of_structure, analyze_symbol
from tests.fixtures.market_data import FakeMarketDataClient, generate_trend_dataset


def test_analysis_snapshot_includes_rsi_and_volume_metadata(tmp_path) -> None:
    settings = Settings(data_storage_path=tmp_path)
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })

    analysis = analyze_symbol(
        market_data=market_data,
        settings=settings,
        scan_run_id="run_test",
        symbol="BTCUSDT",
    )

    assert "rsi" in analysis.entry_snapshot.metadata
    assert "break_of_structure" in analysis.entry_snapshot.metadata
    assert "directional_liquidity_level" in analysis.entry_snapshot.metadata
    assert "directional_liquidity_side" in analysis.entry_snapshot.metadata
    assert "nearest_liquidity_level" in analysis.entry_snapshot.metadata
    assert "nearest_liquidity_side" in analysis.entry_snapshot.metadata
    assert "nearest_distance_to_liquidity_atr" in analysis.entry_snapshot.metadata
    assert "volume_average_20" in analysis.entry_snapshot.metadata
    assert "volume_ratio_vs_average_20" in analysis.entry_snapshot.metadata
    assert 0 <= float(analysis.entry_snapshot.metadata["rsi"]) <= 100


def test_break_of_structure_detects_recent_continuation_break() -> None:
    dataset = generate_trend_dataset(direction="up")
    recent_high = max(float(item["high"]) for item in dataset[-9:-1])
    recent_close_high = max(float(item["close"]) for item in dataset[-9:-1])
    previous_twenty_high = max(float(item["high"]) for item in dataset[-21:-1])
    dataset[-1]["open"] = recent_close_high + 0.05
    dataset[-1]["close"] = recent_close_high + 0.2
    dataset[-1]["high"] = recent_high + 0.2

    assert float(dataset[-1]["close"]) < previous_twenty_high
    assert _detect_break_of_structure(dataset) == "bullish_bos"
