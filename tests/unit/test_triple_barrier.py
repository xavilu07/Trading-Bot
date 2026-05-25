from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.generate_triple_barrier_labels import generate_triple_barrier_labels
from trading_signals.research.triple_barrier import SL_HIT, TIMEOUT, TP_HIT, UNKNOWN, label_triple_barrier


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_tp_before_sl_labels_tp_hit() -> None:
    signal = {
        "timestamp": "2026-05-24T10:00:00+00:00",
        "direction": "long",
        "entry": 100,
        "stop_loss": 95,
        "take_profit": 110,
    }
    bars = [
        {"timestamp": "2026-05-24T11:00:00+00:00", "high": 111, "low": 99, "close": 110},
        {"timestamp": "2026-05-24T12:00:00+00:00", "high": 112, "low": 94, "close": 96},
    ]

    result = label_triple_barrier(signal, bars, time_barrier_bars=2)

    assert result["label"] == TP_HIT
    assert result["label_reason"] == "take_profit_barrier_hit"
    assert result["result_r"] == 2.0
    assert result["bars_to_label"] == 1


def test_sl_before_tp_labels_sl_hit() -> None:
    signal = {
        "timestamp": "2026-05-24T10:00:00+00:00",
        "direction": "long",
        "entry": 100,
        "stop_loss": 95,
        "take_profit": 110,
    }
    bars = [
        {"timestamp": "2026-05-24T11:00:00+00:00", "high": 104, "low": 94, "close": 96},
        {"timestamp": "2026-05-24T12:00:00+00:00", "high": 111, "low": 98, "close": 110},
    ]

    result = label_triple_barrier(signal, bars, time_barrier_bars=2)

    assert result["label"] == SL_HIT
    assert result["label_reason"] == "stop_loss_barrier_hit"
    assert result["result_r"] == -1.0
    assert result["bars_to_label"] == 1


def test_no_touch_before_limit_labels_timeout() -> None:
    signal = {
        "timestamp": "2026-05-24T10:00:00+00:00",
        "direction": "long",
        "entry": 100,
        "stop_loss": 95,
        "take_profit": 110,
    }
    bars = [
        {"timestamp": "2026-05-24T11:00:00+00:00", "high": 104, "low": 98, "close": 101},
        {"timestamp": "2026-05-24T12:00:00+00:00", "high": 105, "low": 97, "close": 102},
    ]

    result = label_triple_barrier(signal, bars, time_barrier_bars=2)

    assert result["label"] == TIMEOUT
    assert result["label_reason"] == "time_barrier_reached"
    assert result["result_r"] == 0.4
    assert result["bars_to_label"] == 2


def test_incomplete_data_labels_unknown() -> None:
    result = label_triple_barrier({"direction": "long", "entry": 100}, [], time_barrier_bars=2)

    assert result["label"] == UNKNOWN
    assert result["label_reason"] == "missing_required_data"


def test_generate_triple_barrier_labels_writes_csv(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "signal_id": "sig_1",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_price": 100,
                "stop_loss": 95,
                "take_profit": 110,
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "mid_range",
                "bars": [
                    {"timestamp": "2026-05-24T11:00:00+00:00", "high": 111, "low": 99, "close": 110},
                ],
            },
            {
                "signal_id": "sig_short",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "ETHUSDT",
                "direction": "short",
                "entry_price": 100,
                "stop_loss": 105,
                "take_profit": 90,
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "OVERLAP",
                "entry_context": "BREAKOUT",
                "trade_location": "mid_range",
                "bars": [
                    {"timestamp": "2026-05-24T11:00:00+00:00", "high": 101, "low": 89, "close": 90},
                ],
            }
        ],
    )

    result = generate_triple_barrier_labels(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        time_barrier_bars=1,
        source="signals",
    )

    output_path = Path(result["output_path"])
    rows = list(csv.DictReader(output_path.open("r", encoding="utf-8")))
    assert output_path.exists()
    assert rows[0]["label"] == TP_HIT
    assert rows[0]["signal_id"] == "sig_1"
    assert any(row["signal_id"] == "sig_short" and row["direction"] == "short" for row in rows)
