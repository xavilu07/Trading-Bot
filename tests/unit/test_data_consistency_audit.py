from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.research.data_consistency_audit import (
    compute_metrics,
    load_canonical_closed_trades,
    run_data_consistency_audit,
    write_data_consistency_audit,
)


def test_canonical_metrics_from_paper_and_live_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 2.0), _trade("sl_hit", -1.0)])
    _write_csv(data_path / "live_trading" / "trades.csv", [_trade("sl_hit", -1.0, symbol="ETHUSDT")])

    trades = load_canonical_closed_trades(data_path)
    metrics = compute_metrics(trades)

    assert metrics["closed_trades"] == 2
    assert metrics["total_r"] == 1.0
    assert metrics["winrate"] == 50.0
    assert metrics["profit_factor"] == 2.0


def test_data_consistency_audit_marks_matching_outcome_report_consistent(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    rows = [_trade("tp_hit", 2.0), _trade("sl_hit", -1.0)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)
    _write_csv(data_path / "live_trading" / "trades.csv", [])
    _write_csv(reports_path / "outcome_intelligence.csv", rows)
    _write_csv(reports_path / "edge_breakdown.csv", [{"group_type": "direction", "group": "long"}])
    _write_csv(reports_path / "setup_rankings.csv", [{"dimension": "setup_type", "value": "MAIN_SIGNAL"}])

    result = run_data_consistency_audit(
        data_path=data_path,
        reports_path=reports_path,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    intelligence = next(item for item in result["systems"] if item["system"] == "Intelligence Reports")

    assert intelligence["classification"] == "CONSISTENT"


def test_data_consistency_audit_detects_critical_mismatch(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 2.0), _trade("sl_hit", -1.0)])
    _write_csv(reports_path / "outcome_intelligence.csv", [_trade("tp_hit", 2.0)])

    result = run_data_consistency_audit(
        data_path=data_path,
        reports_path=reports_path,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    intelligence = next(item for item in result["systems"] if item["system"] == "Intelligence Reports")

    assert intelligence["classification"] == "CRITICAL MISMATCH"
    assert result["status"] == "CRITICAL MISMATCH"


def test_data_consistency_audit_writes_json_and_markdown(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("tp_hit", 1.0)])

    result = run_data_consistency_audit(
        data_path=data_path,
        reports_path=reports_path,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    paths = write_data_consistency_audit(result, reports_path)

    assert paths["json_path"].exists()
    assert paths["markdown_path"].exists()
    assert json.loads(paths["json_path"].read_text(encoding="utf-8"))["audited_systems"]


def _trade(status: str, result_r: float, *, symbol: str = "BTCUSDT") -> dict[str, object]:
    return {
        "symbol": symbol,
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "session": "LONDON",
        "status": status,
        "result_r": result_r,
        "closed_at": "2026-01-01T10:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status", "result_r"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
