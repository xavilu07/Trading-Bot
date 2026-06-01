from __future__ import annotations

import csv
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.research.bot_audit_ai import (
    audit_bot_audit_ai_inputs,
    build_relaxation_shadow_status,
    format_bot_audit_ai_inputs_audit,
    format_bot_audit_ai_markdown,
    generate_bot_audit_ai,
    write_bot_audit_ai,
)


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
    assert paths["inputs_audit_path"].exists()


def test_bot_audit_ai_includes_relaxation_shadow_status(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 1.0)])
    _write_csv(
        data_path / "shadow_relaxation" / "trades.csv",
        [{"symbol": "BTCUSDT", "direction": "long", "status": "open"}],
    )
    _write_csv(
        data_path / "shadow_relaxation" / "skips.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": "80",
                "block_reasons": json.dumps(["breakout_bad_location", "kill_switch_active"]),
                "safe_filters": json.dumps(["breakout_bad_location"]),
                "unsafe_filters": json.dumps(["kill_switch_active"]),
                "skip_reason": "unsafe_or_empty_filters",
            }
        ],
    )

    result = generate_bot_audit_ai(data_path=data_path, reports_path=reports_path)
    markdown = format_bot_audit_ai_markdown(result)

    assert result["relaxation_shadow_status"]["trades_captured"] == 1
    assert result["relaxation_shadow_status"]["skips_captured"] == 1
    assert result["relaxation_shadow_status"]["last_skip_reason"] == "unsafe_or_empty_filters"
    assert result["relaxation_shadow_status"]["top_unsafe_filters"][0]["filter"] == "kill_switch_active"
    assert "## Relaxation Shadow Status" in markdown
    assert "- trades captured: 1" in markdown


def test_relaxation_shadow_status_uses_report_fallbacks_and_detects_strict_shadow(tmp_path: Path) -> None:
    reports_path = tmp_path / "reports"
    _write_csv(
        reports_path / "relaxation_shadow_v1_summary.csv",
        [{"group": "by_direction", "value": "long", "trades": "0"}],
    )
    _write_csv(
        reports_path / "relaxation_shadow_v1_skips.csv",
        [
            {
                "symbol": f"BTC{i}",
                "direction": "long",
                "score": "80",
                "block_reasons": json.dumps(["breakout_bad_location"]),
                "safe_filters": json.dumps(["breakout_bad_location"]),
                "unsafe_filters": json.dumps([]),
                "skip_reason": "unsafe_or_empty_filters",
            }
            for i in range(5)
        ],
    )

    status = build_relaxation_shadow_status(data_path=tmp_path / "data", reports_path=reports_path)

    assert status["trades_captured"] == 0
    assert status["skips_captured"] == 5
    assert status["v1_too_strict"] is True
    assert status["recommendation"] == "loosen shadow only"


def test_bot_audit_ai_inputs_audit_classifies_found_missing_and_stale(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    now = datetime(2026, 1, 3, tzinfo=UTC)
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 1.0)])
    fresh_report = reports_path / "outcome_intelligence.csv"
    stale_report = reports_path / "edge_breakdown.csv"
    _write_csv(fresh_report, [_trade("tp_hit", 1.0)])
    _write_csv(stale_report, [_trade("tp_hit", 1.0)])
    stale_ts = (now - timedelta(hours=72)).timestamp()
    os.utime(stale_report, (stale_ts, stale_ts))
    fresh_ts = (now - timedelta(hours=2)).timestamp()
    os.utime(fresh_report, (fresh_ts, fresh_ts))
    os.utime(data_path / "paper_trading" / "trades.csv", (fresh_ts, fresh_ts))

    audit = audit_bot_audit_ai_inputs(data_path=data_path, reports_path=reports_path, now=now)
    by_name = {item["name"]: item for item in audit["inputs"]}

    assert by_name["canonical_trades"]["classification"] == "FOUND"
    assert by_name["outcome_intelligence"]["classification"] == "FOUND"
    assert by_name["edge_breakdown"]["classification"] == "STALE"
    assert by_name["setup_rankings"]["classification"] == "MISSING"
    assert "BOT_AUDIT_AI Inputs Audit" in format_bot_audit_ai_inputs_audit(audit)


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
