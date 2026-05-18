from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.analyze_performance_gate import analyze_performance_gate, format_analysis


def write_scheduler_window(path: Path) -> None:
    path.parent.mkdir(parents=True)
    window = [
        {
            "results": [
                {
                    "symbol": "BTCUSDT",
                    "signal": {
                        "symbol": "BTCUSDT",
                        "decision": "long",
                        "dedupe_key": "btc|long|1",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "performance_gate": gate("PRIORITIZE", would_prioritize=True, confidence="HIGH"),
                },
                {
                    "symbol": "ETHUSDT",
                    "signal": {
                        "symbol": "ETHUSDT",
                        "decision": "short",
                        "dedupe_key": "eth|short|1",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "performance_gate": gate("WOULD_BLOCK", would_block=True, confidence="MEDIUM"),
                },
                {
                    "symbol": "SOLUSDT",
                    "signal": {
                        "symbol": "SOLUSDT",
                        "decision": "long",
                        "dedupe_key": "sol|long|1",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "performance_gate": gate("WOULD_BLOCK", would_block=True, confidence="HIGH"),
                },
                {
                    "symbol": "XRPUSDT",
                    "signal": {
                        "symbol": "XRPUSDT",
                        "decision": "long",
                        "dedupe_key": "xrp|long|1",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "performance_gate": gate("ALLOW"),
                },
                {
                    "symbol": "BNBUSDT",
                    "signal": {
                        "symbol": "BNBUSDT",
                        "decision": "long",
                        "dedupe_key": "bnb|long|1",
                        "created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "performance_gate": gate("CAUTION"),
                },
            ]
        }
    ]
    path.write_text(json.dumps(window), encoding="utf-8")


def gate(action: str, *, would_block: bool = False, would_prioritize: bool = False, confidence: str = "MEDIUM") -> dict[str, object]:
    return {
        "mode": "SOFT",
        "action": action,
        "would_block": would_block,
        "would_prioritize": would_prioritize,
        "confidence": confidence,
        "reasons": ["reason"],
        "risks": ["risk"] if would_block else [],
        "scores": {
            "meta_decision_score": 70,
            "trade_quality_score": 60,
            "historical_edge_score": 55,
        },
    }


def write_trades(data_path: Path) -> None:
    trades_dir = data_path / "paper_trading"
    trades_dir.mkdir(parents=True)
    rows = [
        {"trade_id": "paper_btc", "dedupe_key": "btc|long|1|paper", "symbol": "BTCUSDT", "direction": "long", "setup_type": "MAIN_SIGNAL", "status": "tp2_hit", "result_r": "2.0"},
        {"trade_id": "paper_eth", "dedupe_key": "eth|short|1|paper", "symbol": "ETHUSDT", "direction": "short", "setup_type": "MAIN_SIGNAL", "status": "sl_hit", "result_r": "-1.0"},
        {"trade_id": "paper_sol", "dedupe_key": "sol|long|1|paper", "symbol": "SOLUSDT", "direction": "long", "setup_type": "MAIN_SIGNAL", "status": "tp_hit", "result_r": "1.5"},
        {"trade_id": "paper_xrp", "dedupe_key": "xrp|long|1|paper", "symbol": "XRPUSDT", "direction": "long", "setup_type": "MAIN_SIGNAL", "status": "sl_hit", "result_r": "-1.0"},
        {"trade_id": "paper_bnb", "dedupe_key": "bnb|long|1|paper", "symbol": "BNBUSDT", "direction": "long", "setup_type": "MAIN_SIGNAL", "status": "expired", "result_r": "-0.5"},
    ]
    with (trades_dir / "trades.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_analyze_performance_gate_counts_actions_and_outcomes(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    scheduler_window_path = data_path / "scheduler_diagnostic_window.json"
    write_scheduler_window(scheduler_window_path)
    write_trades(data_path)

    result = analyze_performance_gate(data_path=data_path, scheduler_window_path=scheduler_window_path)

    assert result["total_gate_events"] == 5
    assert result["matched_outcomes"] == 5
    assert result["action_counts"] == {
        "PRIORITIZE": 1,
        "ALLOW": 1,
        "CAUTION": 1,
        "WOULD_BLOCK": 2,
    }
    assert result["metrics_by_action"]["PRIORITIZE"]["winrate"] == 100.0
    assert result["metrics_by_action"]["PRIORITIZE"]["avg_r"] == 2.0
    assert result["metrics_by_action"]["WOULD_BLOCK"]["winrate"] == 50.0
    assert result["metrics_by_action"]["WOULD_BLOCK"]["total_r"] == 0.5
    assert result["would_block_impact"]["losses_avoided"] == 1
    assert result["would_block_impact"]["winning_trades_would_have_been_blocked"] == 1
    assert result["prioritize_vs_rest"]["prioritize_has_better_avg_r"] is True


def test_format_analysis_includes_required_sections(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    scheduler_window_path = data_path / "scheduler_diagnostic_window.json"
    write_scheduler_window(scheduler_window_path)
    write_trades(data_path)

    text = format_analysis(analyze_performance_gate(data_path=data_path, scheduler_window_path=scheduler_window_path))

    assert "Performance Gate Impact" in text
    assert "WOULD_BLOCK impact" in text
    assert "PRIORITIZE vs rest" in text
    assert "PRIORITIZE: count 1" in text
