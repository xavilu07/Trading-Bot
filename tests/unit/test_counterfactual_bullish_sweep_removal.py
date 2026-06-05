from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.counterfactual_bullish_sweep_removal import (
    analyze_counterfactual_bullish_sweep_removal,
    write_counterfactual_bullish_sweep_removal_report,
)


def test_counterfactual_removing_losing_bullish_sweep_improves_metrics(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, 1.5),
            _trade(2, -1.0),
            _trade(3, -1.0, liquidity_sweep="bullish_sweep"),
            _trade(4, -1.0, liquidity_context="sweep:bullish_sweep"),
        ],
    )

    result = analyze_counterfactual_bullish_sweep_removal(data_path=data_path)

    assert result["current"]["trades"] == 4
    assert result["without_bullish_sweep"]["trades"] == 2
    assert result["deltas"]["total_r_delta"] == 2.0
    assert result["deltas"]["pf_delta"] > 0
    assert "improves" in result["answer"]


def test_counterfactual_no_bullish_sweep_has_no_effect(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, 1.5), _trade(2, -1.0)])

    result = analyze_counterfactual_bullish_sweep_removal(data_path=data_path)

    assert result["deltas"]["trades_removed"] == 0
    assert result["current"] == result["without_bullish_sweep"]
    assert "No bullish_sweep trades" in result["answer"]


def test_counterfactual_report_is_written(tmp_path: Path) -> None:
    result = analyze_counterfactual_bullish_sweep_removal(data_path=tmp_path / "data")
    path = write_counterfactual_bullish_sweep_removal_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "COUNTERFACTUAL_BULLISH_SWEEP_REMOVAL" in text
    assert "PF delta" in text


def _trade(index: int, result_r: float, *, liquidity_sweep: str = "", liquidity_context: str = "") -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": "BTCUSDT",
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "closed_at": "2026-06-01T12:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "liquidity_context": liquidity_context,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
