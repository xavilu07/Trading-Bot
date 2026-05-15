from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.generate_missed_opportunities import generate_missed_opportunities
from trading_signals.memory.missed_opportunity import analyze_missed_opportunity


def test_signal_that_would_have_won_is_missed_win() -> None:
    signal = {"direction": "long", "entry_price": 100, "stop_loss": 99, "take_profit": 102, "timestamp": "2026-01-01T00:00:00+00:00"}
    candles = [
        {"open_time": "2026-01-01T01:00:00+00:00", "high": 101.0, "low": 99.5},
        {"open_time": "2026-01-01T02:00:00+00:00", "high": 102.1, "low": 100.5},
    ]

    result = analyze_missed_opportunity(signal, candles)

    assert result["missed_opportunity_type"] == "MISSED_WIN"
    assert result["max_r"] >= 2
    assert result["time_to_resolution"] == 2


def test_signal_that_would_have_lost_is_good_rejection() -> None:
    signal = {"direction": "short", "entry_price": 100, "stop_loss": 101, "take_profit": 98}
    candles = [{"high": 101.2, "low": 99.5}]

    result = analyze_missed_opportunity(signal, candles)

    assert result["missed_opportunity_type"] == "GOOD_REJECTION"
    assert result["min_r"] <= -1


def test_signal_without_resolution_is_neutral() -> None:
    signal = {"direction": "long", "entry_price": 100, "stop_loss": 99, "take_profit": 102}
    candles = [{"high": 100.7, "low": 99.4}]

    result = analyze_missed_opportunity(signal, candles)

    assert result["missed_opportunity_type"] == "NEUTRAL"


def test_generate_missed_opportunities_writes_csv_with_incomplete_data(tmp_path: Path, monkeypatch) -> None:
    data_path = tmp_path / "data"
    logs_path = tmp_path / "logs"
    reports_path = tmp_path / "reports"
    activity = data_path / "bot_activity" / "signals_log.jsonl"
    activity.parent.mkdir(parents=True)
    activity.write_text(
        json.dumps(
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_price": 100,
                "stop_loss": 99,
                "take_profit": 102,
                "score": 90,
                "status": "no_trade",
                "rejection_reasons": ["test_reject"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeProvider:
        def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300):
            return [{"open_time": "2026-01-01T01:00:00+00:00", "high": 102.5, "low": 100}]

    monkeypatch.setattr("scripts.generate_missed_opportunities._safe_provider", lambda: FakeProvider())
    result = generate_missed_opportunities(data_path, reports_path, logs_path)

    output = reports_path / "missed_opportunities.csv"
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert output.exists()
    assert result["summary"]["counts"]["MISSED_WIN"] == 1
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["missed_opportunity_type"] == "MISSED_WIN"

