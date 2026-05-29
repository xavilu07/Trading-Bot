from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.bot_audit_ai import generate_bot_audit_ai, write_bot_audit_ai


def test_bot_audit_ai_generates_with_missing_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 1.0), _trade("sl_hit", -1.0)])

    result = generate_bot_audit_ai(data_path=data_path, reports_path=reports_path)

    assert result["executive_summary"]["closed_trades"] == 2
    assert result["executive_summary"]["risk_level"] in {"HIGH", "MEDIUM", "LOW"}
    assert result["tomorrow_priorities"]


def test_bot_audit_ai_uses_edge_and_experiment_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 2.0), _trade("sl_hit", -1.0)])
    _write_json(
        reports_path / "post_consistency_edge_recalc.json",
        {
            "hypotheses": [
                {"hypothesis": "SHADOW_SEND_CURRENT_REJECT", "classification": "CONFIRMED_EDGE", "sample_size": 12, "total_r": 5.0, "winrate": 60, "profit_factor": 2.0},
                {"hypothesis": "CHOPPY_RANGE", "classification": "TOXIC_CONTEXT", "sample_size": 8, "total_r": -3.0, "winrate": 25, "profit_factor": 0.4},
            ]
        },
    )
    _write_json(
        reports_path / "shadow_send_current_reject_deep_dive.json",
        {"metrics": {"closed_trades": 14, "total_r": 7.3887, "winrate": 57.14, "profit_factor": 2.6548}},
    )
    _write_csv(
        reports_path / "shadow_send_current_reject_rejection_reasons.csv",
        [
            {"reason": "breakout_bad_location", "classification": "SAFE_TO_RELAX", "sample_size": 5, "total_r": 4.4, "winrate": 60, "profit_factor": 3.2},
            {"reason": "short_shadow_mode", "classification": "NEED_MORE_DATA", "sample_size": 2, "total_r": -1.1, "winrate": 0, "profit_factor": 0},
        ],
    )

    result = generate_bot_audit_ai(data_path=data_path, reports_path=reports_path)

    assert result["edge_detection"]["confirmed_edge"][0]["name"] == "SHADOW_SEND_CURRENT_REJECT"
    assert result["edge_detection"]["toxic_context"][0]["name"] == "CHOPPY_RANGE"
    assert result["experiment_tracking"]["winning_experiments"]
    assert result["rejection_analysis"]["most_expensive_rejection_reasons"][0]["reason"] == "breakout_bad_location"


def test_bot_audit_ai_writes_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 1.0)])

    result = generate_bot_audit_ai(data_path=data_path, reports_path=reports_path)
    paths = write_bot_audit_ai(result, reports_path)

    assert paths["markdown_path"].exists()
    assert paths["json_path"].exists()
    payload = json.loads(paths["json_path"].read_text(encoding="utf-8"))
    assert payload["dataset"] == "data/paper_trading/trades.csv"
    assert "executive_summary" in payload


def _trade(status: str, result_r: float) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "session": "OVERLAP",
        "status": status,
        "result_r": result_r,
        "closed_at": "2026-01-01T10:00:00+00:00",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status", "result_r"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
