from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.range_penalty_shadow import (
    analyze_range_penalty_shadow,
    load_research_rows,
    write_range_penalty_reports,
)


def test_range_penalty_shadow_detects_possible_destroyed_edge() -> None:
    rows = [
        _row(result_r=1.0, penalty=True, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
        _row(result_r=1.2, penalty=True, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
        _row(result_r=0.8, penalty=True, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
        _row(result_r=1.0, penalty=True, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
        _row(result_r=0.6, penalty=True, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
        _row(result_r=-1.0, penalty=False, direction="short", market_regime="HIGH_VOLATILITY", entry_context="CHOPPY_RANGE"),
    ]

    result = analyze_range_penalty_shadow(rows, min_trades=5)

    assert result["range_penalty_rows"] == 5
    assert result["top_edge_destroyed_candidates"]
    assert result["top_edge_destroyed_candidates"][0]["shadow_interpretation"] == "RANGE_PENALTY_MAY_DESTROY_EDGE"


def test_range_penalty_shadow_detects_protective_penalty() -> None:
    rows = [
        _row(result_r=-1.0, penalty=True),
        _row(result_r=-1.0, penalty=True),
        _row(result_r=-0.5, penalty=True),
        _row(result_r=-1.2, penalty=True),
        _row(result_r=0.2, penalty=True),
        _row(result_r=1.0, penalty=False),
    ]

    result = analyze_range_penalty_shadow(rows, min_trades=5)

    assert result["top_protective_candidates"]
    assert result["top_protective_candidates"][0]["recommended_action"] == "keep_current_penalty"


def test_range_penalty_shadow_uses_only_canonical_trade_source(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "short",
                "status": "tp_hit",
                "result_r": "1",
                "penalties": json.dumps(["market_structure_range_penalty"]),
                "market_regime": "HIGH_VOLATILITY",
                "entry_context": "CHOPPY_RANGE",
            }
        ],
    )
    _write_csv(
        reports_path / "meta_dataset.csv",
        [
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "label": "1",
                "result_r": "2",
                "has_market_structure_range_penalty": "true",
                "market_regime": "HIGH_VOLATILITY",
                "entry_context": "CHOPPY_RANGE",
            }
        ],
    )

    rows = load_research_rows(data_path, reports_path)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTCUSDT"


def test_range_penalty_shadow_writes_reports(tmp_path: Path) -> None:
    result = analyze_range_penalty_shadow([_row(result_r=1.0, penalty=True)], min_trades=1)
    paths = write_range_penalty_reports(result, tmp_path / "reports")

    assert paths["csv_path"].exists()
    assert paths["json_path"].exists()
    assert "range_penalty_shadow" in paths["json_path"].name


def _row(
    *,
    result_r: float,
    penalty: bool,
    direction: str = "long",
    market_regime: str = "TRENDING",
    entry_context: str = "BREAKOUT",
) -> dict[str, object]:
    return {
        "symbol": "TESTUSDT",
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "market_regime": market_regime,
        "session": "LONDON",
        "entry_context": entry_context,
        "trade_location": "mid_range",
        "result_r": result_r,
        "penalties": ["market_structure_range_penalty"] if penalty else [],
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
