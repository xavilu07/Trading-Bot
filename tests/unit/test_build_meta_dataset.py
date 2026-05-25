from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.build_meta_dataset import build_meta_dataset, format_summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_meta_dataset_is_created_with_joined_features(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    data = tmp_path / "data"
    write_csv(
        reports / "triple_barrier_labels.csv",
        [
            {
                "signal_id": "sig_1",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "label": "TP_HIT",
                "label_reason": "take_profit_barrier_hit",
                "result_r": "2",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "mid_range",
                "setup_type": "MAIN_SIGNAL",
            }
        ],
    )
    write_jsonl(
        data / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": 90,
                "trend_entry": "bullish",
                "trend_higher": "bullish",
                "rsi": 55,
                "body_ratio": 0.7,
                "volume_ratio": 1.5,
                "atr": 100,
                "distance_to_liquidity_atr": 1.2,
                "liquidity_sweep": "bullish_sweep",
                "break_of_structure": "bullish_bos",
                "raw_summary": {"signal_id": "sig_1"},
            }
        ],
    )

    result = build_meta_dataset(data_path=data, logs_path=tmp_path / "logs", reports_path=reports)

    row = result["rows"][0]
    assert row["label"] == "1"
    assert row["score"] == 90
    assert row["timeframe_alignment"] == "true"
    assert row["liquidity_sweep"] == "bullish_sweep"
    assert Path(result["output_path"]).exists()


def test_meta_dataset_handles_unknown_label_without_breaking(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(
        reports / "triple_barrier_labels.csv",
        [
            {
                "signal_id": "sig_unknown",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "ETHUSDT",
                "direction": "short",
                "label": "UNKNOWN",
                "label_reason": "missing_price_path",
                "result_r": "",
            }
        ],
    )

    result = build_meta_dataset(data_path=tmp_path / "data", logs_path=tmp_path / "logs", reports_path=reports)

    assert result["rows"][0]["label"] == ""
    assert result["rows"][0]["direction"] == "short"
    assert result["summary"]["unknown_labels"] == 1
    assert "Unknown: 1" in format_summary(result["summary"])


def test_meta_dataset_extracts_flags_and_counts(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    data = tmp_path / "data"
    write_csv(
        reports / "triple_barrier_labels.csv",
        [
            {
                "signal_id": "sig_flags",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "SOLUSDT",
                "direction": "long",
                "label": "SL_HIT",
                "label_reason": "stop_loss_barrier_hit",
                "result_r": "-1",
            }
        ],
    )
    write_jsonl(
        data / "bot_activity" / "signals_log.jsonl",
        [
            {
                "raw_summary": {"signal_id": "sig_flags"},
                "symbol": "SOLUSDT",
                "direction": "long",
                "avoidance_warnings": ["against_htf", "low_volume", "dirty_sideways_market"],
                "penalties": ["market_structure_range_penalty:10", "timeframe_alignment_penalty:10", "secondary_confluence_bonus:+15"],
            }
        ],
    )

    result = build_meta_dataset(data_path=data, logs_path=tmp_path / "logs", reports_path=reports)
    row = result["rows"][0]

    assert row["has_against_htf"] is True
    assert row["has_low_volume"] is True
    assert row["has_dirty_sideways_market"] is True
    assert row["has_market_structure_range_penalty"] is True
    assert row["has_timeframe_alignment_penalty"] is True
    assert row["has_secondary_confluence_bonus"] is True
    assert row["warnings_count"] == 3
    assert row["penalties_count"] == 6


def test_meta_dataset_writes_csv(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(
        reports / "triple_barrier_labels.csv",
        [
            {
                "signal_id": "sig_1",
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "label": "TP_HIT",
                "label_reason": "take_profit_barrier_hit",
                "result_r": "1",
            }
        ],
    )

    result = build_meta_dataset(data_path=tmp_path / "data", logs_path=tmp_path / "logs", reports_path=reports)

    rows = list(csv.DictReader(Path(result["output_path"]).open("r", encoding="utf-8")))
    assert rows
    assert rows[0]["signal_id"] == "sig_1"
    assert "has_against_htf" in rows[0]
