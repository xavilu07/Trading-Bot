from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.generate_dashboard import _load_closed_trades as load_dashboard_trades
from scripts.generate_outcome_intelligence import load_closed_trades as load_outcome_trades
from scripts.generate_performance_report import load_closed_trades as load_performance_trades
from scripts.generate_setup_rankings import load_closed_trades as load_setup_ranking_trades
from scripts.run_backtest_runner import load_real_trades
from trading_signals.data.canonical_trade_source import load_canonical_closed_trades
from trading_signals.research.context_toxicity_deep_dive import load_context_toxicity_records
from trading_signals.research.london_short_edge_attribution import load_london_short_research_rows
from trading_signals.research.range_penalty_shadow import load_research_rows


def test_all_full_trade_systems_use_canonical_trade_source(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    canonical_rows = [
        _trade("BTCUSDT", "long", "LONDON", "tp_hit", 2.0),
        _trade("ETHUSDT", "short", "LONDON", "sl_hit", -1.0),
    ]
    _write_csv(data_path / "paper_trading" / "trades.csv", canonical_rows)
    _write_csv(data_path / "paper_trading" / "shadow_signals.csv", [_trade("SOLUSDT", "short", "LONDON", "tp_hit", 5.0)])
    _write_csv(data_path / "live_trading" / "trades.csv", [_trade("BNBUSDT", "long", "NEW_YORK", "tp_hit", 3.0)])
    _write_csv(reports_path / "meta_dataset.csv", [_trade("ADAUSDT", "short", "LONDON", "tp_hit", 4.0)])
    _write_jsonl(data_path / "bot_activity" / "signals_log.jsonl", [{"symbol": "XRPUSDT", "direction": "short", "result_r": 9.0}])

    canonical_count = len(load_canonical_closed_trades(data_path))
    counts = {
        "dashboard": len(load_dashboard_trades(data_path)),
        "outcome_intelligence": len(load_outcome_trades(data_path)),
        "performance_report": len(load_performance_trades(data_path)),
        "setup_rankings": len(load_setup_ranking_trades(data_path)),
        "backtest_runner": len(load_real_trades(data_path)),
        "context_toxicity": len(load_context_toxicity_records(data_path, reports_path)),
        "range_penalty_shadow": len(load_research_rows(data_path, reports_path)),
    }

    assert canonical_count == 2
    assert counts == {key: canonical_count for key in counts}


def test_london_short_analysis_uses_canonical_subset_only(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade("BTCUSDT", "short", "LONDON", "tp_hit", 1.0),
            _trade("ETHUSDT", "short", "NEW_YORK", "tp_hit", 1.0),
            _trade("SOLUSDT", "long", "LONDON", "tp_hit", 1.0),
        ],
    )
    _write_csv(data_path / "paper_trading" / "shadow_signals.csv", [_trade("SHADOW", "short", "LONDON", "tp_hit", 1.0)])
    _write_csv(reports_path / "meta_dataset.csv", [_trade("META", "short", "LONDON", "tp_hit", 1.0)])

    rows = load_london_short_research_rows(data_path, reports_path)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"


def _trade(symbol: str, direction: str, session: str, status: str, result_r: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "direction": direction,
        "session": session,
        "setup_type": "MAIN_SIGNAL",
        "entry_context": "PULLBACK",
        "market_regime": "TRENDING",
        "trade_location": "mid_range",
        "status": status,
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


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
