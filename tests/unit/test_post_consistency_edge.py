from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.post_consistency_edge import (
    recalculate_post_consistency_edge,
    write_post_consistency_edge_reports,
)


def test_post_consistency_edge_classifies_confirmed_possible_toxic_and_no_edge(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = []
    rows.extend(_trade("BTC", "short", "LONDON", "PULLBACK", "TRENDING", 1.0) for _ in range(10))
    rows.extend(_trade("ETH", "long", "OVERLAP", "BREAKOUT", "HIGH_VOLATILITY", -1.0) for _ in range(5))
    rows.extend(_trade("SOL", "long", "LONDON", "CHOPPY_RANGE", "RANGING", -1.0) for _ in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = recalculate_post_consistency_edge(data_path=data_path, min_trades=5)
    london_short = _find(result, "LONDON_SHORT")
    high_vol_long = _find(result, "HIGH_VOLATILITY_LONG")
    choppy = _find(result, "CONTEXT_CHOPPY_RANGE")
    setup_unknown = _find(result, "CONTEXT_SETUP_UNKNOWN")

    assert london_short["classification"] == "CONFIRMED_EDGE"
    assert high_vol_long["classification"] == "TOXIC_CONTEXT"
    assert choppy["classification"] == "TOXIC_CONTEXT"
    assert setup_unknown["classification"] == "NO_EDGE"


def test_shadow_send_current_reject_uses_only_canonical_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    canonical_rows = [_trade("BTC", "long", "OVERLAP", "BREAKOUT", "TRENDING", 1.0) for _ in range(6)]
    _write_csv(data_path / "paper_trading" / "trades.csv", canonical_rows)
    _write_csv(data_path / "paper_trading" / "shadow_signals.csv", [_trade("SHADOW", "long", "OVERLAP", "BREAKOUT", "TRENDING", 10.0)])

    result = recalculate_post_consistency_edge(data_path=data_path, min_trades=5)
    shadow = _find(result, "SHADOW_SEND_CURRENT_REJECT")

    assert result["records_analyzed"] == 6
    assert shadow["sample_size"] <= 6


def test_post_consistency_edge_writes_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade("BTC", "long", "OVERLAP", "BREAKOUT", "TRENDING", 1.0)])

    result = recalculate_post_consistency_edge(data_path=data_path)
    paths = write_post_consistency_edge_reports(result, reports_path)

    assert paths["json_path"].exists()
    assert paths["csv_path"].exists()
    assert paths["summary_path"].exists()
    assert json.loads(paths["json_path"].read_text(encoding="utf-8"))["dataset"] == "data/paper_trading/trades.csv"


def _find(result: dict[str, object], hypothesis: str) -> dict[str, object]:
    return next(row for row in result["hypotheses"] if row["hypothesis"] == hypothesis)


def _trade(symbol: str, direction: str, session: str, entry_context: str, market_regime: str, result_r: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "direction": direction,
        "session": session,
        "setup_type": "MAIN_SIGNAL",
        "entry_context": entry_context,
        "market_regime": market_regime,
        "trade_location": "mid_range",
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "risk_reward": 2.0,
        "closed_at": "2026-01-01T10:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
