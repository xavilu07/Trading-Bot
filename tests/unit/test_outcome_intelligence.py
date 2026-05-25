from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_outcome_intelligence import generate_outcome_intelligence
from trading_signals.memory.outcome_intelligence import analyze_trade_outcome


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_clean_win_classifies_as_clean_win() -> None:
    result = analyze_trade_outcome({"result_r": "2", "mfe_r": "2.2", "mae_r": "-0.2", "bars_held": "4", "status": "tp2_hit"})

    assert result["outcome_type"] == "CLEAN_WIN"
    assert result["outcome_grade"] in {"A", "A+"}
    assert result["post_entry_behavior"] == "STRONG_CONTINUATION"


def test_win_with_high_mae_classifies_as_dirty_win() -> None:
    result = analyze_trade_outcome({"result_r": "1.2", "mfe_r": "2.0", "mae_r": "-1.2", "bars_held": "18", "status": "tp_hit"})

    assert result["outcome_type"] == "DIRTY_WIN"
    assert result["post_entry_behavior"] == "CHOPPY_RECOVERY"
    assert result["mae_pressure"] == 1.2


def test_strong_loss_classifies_as_bad_loss() -> None:
    result = analyze_trade_outcome({"result_r": "-1", "mfe_r": "0.1", "mae_r": "-1.5", "bars_held": "3", "status": "sl_hit"})

    assert result["outcome_type"] == "BAD_LOSS"
    assert result["outcome_grade"] == "TRASH"
    assert "loss agresivo: MAE alto o SL rápido" in result["outcome_risks"]


def test_timeout_classifies_as_timeout() -> None:
    result = analyze_trade_outcome({"result_r": "0", "bars_held": "30", "exit_reason": "timeout"})

    assert result["outcome_type"] == "TIMEOUT"
    assert result["post_entry_behavior"] == "SLOW_GRIND"


def test_missing_columns_do_not_break() -> None:
    result = analyze_trade_outcome({"status": "tp_hit"})

    assert result["outcome_type"] == "UNKNOWN"
    assert result["outcome_quality_score"] == 50.0
    assert result["mfe_efficiency"] is None


def test_generate_outcome_intelligence_writes_csv(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "near_support",
                "status": "tp2_hit",
                "result_r": "2",
                "mfe_r": "2.2",
                "mae_r": "-0.2",
                "bars_held": "4",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "status": "sl_hit",
                "result_r": "-1",
                "mfe_r": "0.1",
                "mae_r": "-1.5",
                "bars_held": "3",
            },
        ],
    )

    result = generate_outcome_intelligence(data_path, reports_path)
    output = reports_path / "outcome_intelligence.csv"

    assert output.exists()
    assert result["summary"]["counts"]["CLEAN_WIN"] == 1
    assert result["summary"]["counts"]["BAD_LOSS"] == 1
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["outcome_type"] == "CLEAN_WIN"
    assert rows[1]["direction"] == "short"
