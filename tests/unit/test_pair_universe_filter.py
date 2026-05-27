from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.market.pair_universe_filter import PairUniverseFilterConfig, evaluate_pair_universe


NOW = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def candles(
    *,
    count: int = 300,
    volume: float = 1000.0,
    open_: float = 100.0,
    close: float = 101.0,
    high: float = 102.0,
    low: float = 99.0,
) -> list[dict[str, float]]:
    return [
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}
        for _ in range(count)
    ]


def fetch_factory(mapping: dict[str, list[dict[str, float]]]):
    def fetch(symbol: str, timeframe: str, *, limit: int):
        return mapping.get(symbol, [])[-limit:]

    return fetch


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_pair_universe_filter_passes_clean_symbol_in_shadow_mode(tmp_path: Path) -> None:
    result = evaluate_pair_universe(
        symbols=["BTCUSDT"],
        fetch_ohlcv=fetch_factory({"BTCUSDT": candles()}),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(),
        now=NOW,
    )

    assert result["mode"] == "shadow_only"
    assert result["passed_symbols"] == ["BTCUSDT"]
    assert result["failed_symbols"] == []
    assert result["impact_estimate"]["current_mode_keeps_all"] is True


def test_pair_universe_filter_flags_market_quality_reasons(tmp_path: Path) -> None:
    result = evaluate_pair_universe(
        symbols=["BADUSDT"],
        fetch_ohlcv=fetch_factory(
            {
                "BADUSDT": candles(
                    count=100,
                    volume=10,
                    open_=100,
                    close=120,
                    high=150,
                    low=80,
                )
            }
        ),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(
            min_volume=100,
            max_spread_pct=5,
            min_volatility_pct=0.5,
            max_volatility_pct=20,
            min_history_candles=220,
        ),
        now=NOW,
    )

    reasons = result["failed_symbols"][0]["reasons"]
    assert "insufficient_history" in reasons
    assert "volume_below_min" in reasons
    assert "spread_above_max" in reasons
    assert "volatility_above_max" in reasons


def test_pair_universe_filter_respects_blacklist_and_whitelist(tmp_path: Path) -> None:
    result = evaluate_pair_universe(
        symbols=["BTCUSDT", "DOGEUSDT"],
        fetch_ohlcv=fetch_factory({"BTCUSDT": candles(), "DOGEUSDT": candles()}),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(blacklist=["BTCUSDT"], whitelist=["BTCUSDT"]),
        now=NOW,
    )

    by_symbol = {item["symbol"]: item["reasons"] for item in result["failed_symbols"]}
    assert by_symbol["BTCUSDT"] == ["blacklisted"]
    assert by_symbol["DOGEUSDT"] == ["not_in_whitelist"]


def test_pair_universe_filter_flags_too_many_recent_rejections(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "bot_activity" / "signals_log.jsonl",
        [
            {"symbol": "ETHUSDT", "status": "rejected", "timestamp": (NOW - timedelta(hours=1)).isoformat()},
            {"symbol": "ETHUSDT", "status": "no_trade", "timestamp": (NOW - timedelta(hours=2)).isoformat()},
        ],
    )

    result = evaluate_pair_universe(
        symbols=["ETHUSDT"],
        fetch_ohlcv=fetch_factory({"ETHUSDT": candles()}),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(rejection_threshold=2),
        now=NOW,
    )

    assert "too_many_recent_rejections" in result["failed_symbols"][0]["reasons"]


def test_pair_universe_filter_flags_negative_recent_performance(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {"symbol": "AVAXUSDT", "status": "sl_hit", "result_r": "-1", "closed_at": (NOW - timedelta(days=1)).isoformat()},
            {"symbol": "AVAXUSDT", "status": "sl_hit", "result_r": "-0.8", "closed_at": (NOW - timedelta(days=2)).isoformat()},
            {"symbol": "AVAXUSDT", "status": "sl_hit", "result_r": "-0.7", "closed_at": (NOW - timedelta(days=3)).isoformat()},
        ],
    )

    result = evaluate_pair_universe(
        symbols=["AVAXUSDT"],
        fetch_ohlcv=fetch_factory({"AVAXUSDT": candles()}),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(performance_min_trades=3, min_recent_avg_r=-0.5),
        now=NOW,
    )

    assert "recent_performance_too_negative" in result["failed_symbols"][0]["reasons"]


def test_pair_universe_filter_disabled_does_not_fail_symbols(tmp_path: Path) -> None:
    result = evaluate_pair_universe(
        symbols=["BADUSDT"],
        fetch_ohlcv=fetch_factory({"BADUSDT": []}),
        data_path=tmp_path,
        timeframe="1h",
        config=PairUniverseFilterConfig(mode="disabled", blacklist=["BADUSDT"]),
        now=NOW,
    )

    assert result["failed_symbols"] == []
    assert result["passed_symbols"] == ["BADUSDT"]
