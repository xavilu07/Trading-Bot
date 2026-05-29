from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.shadow_current_reject_deep_dive import (
    analyze_shadow_send_current_reject,
    write_shadow_send_current_reject_reports,
)


def test_shadow_current_reject_details_use_canonical_rows(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade("BTCUSDT", result_r=1.0) for _ in range(6)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)
    _write_csv(data_path / "paper_trading" / "shadow_signals.csv", [_trade("SHADOWUSDT", result_r=10.0)])

    result = analyze_shadow_send_current_reject(data_path=data_path, min_trades=5)

    assert result["records_analyzed"] == 6
    assert result["sample_size"] <= 6
    assert all(row["symbol"] != "SHADOWUSDT" for row in result["trades"])


def test_shadow_current_reject_classifies_safe_to_relax(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade("BTCUSDT", result_r=1.0) for _ in range(6)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_shadow_send_current_reject(data_path=data_path, min_trades=5)
    classifications = {row["reason"]: row["classification"] for row in result["rejection_reason_impact"]}

    assert classifications["edge_activation_requires_overlap_session"] == "SAFE_TO_RELAX"


def test_shadow_current_reject_writes_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("BTCUSDT", result_r=1.0)])

    result = analyze_shadow_send_current_reject(data_path=data_path)
    paths = write_shadow_send_current_reject_reports(result, reports_path)

    assert paths["json_path"].exists()
    assert paths["trades_csv_path"].exists()
    assert paths["reasons_csv_path"].exists()
    assert paths["summary_path"].exists()
    assert json.loads(paths["json_path"].read_text(encoding="utf-8"))["scope"] == "SHADOW_SEND_CURRENT_REJECT"


def _trade(symbol: str, *, result_r: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "direction": "long",
        "session": "LONDON",
        "setup_type": "MAIN_SIGNAL",
        "score": 82,
        "entry_context": "BREAKOUT",
        "market_regime": "TRENDING",
        "trade_location": "mid_range",
        "risk_reward": 2.0,
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "closed_at": "2026-01-01T10:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
