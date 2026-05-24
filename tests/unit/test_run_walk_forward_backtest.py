from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.run_walk_forward_backtest import format_walk_forward, run_walk_forward_backtest


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def trade(
    signal_id: str,
    closed_at: datetime,
    result_r: float,
    *,
    direction: str = "long",
    setup_type: str = "MAIN_SIGNAL",
    market_regime: str = "TRENDING",
) -> dict[str, object]:
    return {
        "signal_id": signal_id,
        "closed_at": closed_at.isoformat(),
        "created_at": (closed_at - timedelta(hours=1)).isoformat(),
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "direction": direction,
        "setup_type": setup_type,
        "market_regime": market_regime,
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "mid_range",
    }


def rows_by_group(result: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["group_type"]), str(row["group"])): row
        for row in result["rows"]
        if isinstance(row, dict)
    }


def test_walk_forward_insufficient_windows_do_not_break(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    write_csv(
        tmp_path / "data" / "live_trading" / "trades.csv",
        [
            trade("sig_1", base + timedelta(days=1), 1),
            trade("sig_2", base + timedelta(days=11), -1),
        ],
    )

    result = run_walk_forward_backtest(
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports",
        train_days=10,
        test_days=5,
        step_days=5,
        min_trades=5,
    )

    overall = rows_by_group(result)[("OVERALL", "ALL")]
    assert overall["overfit_warning"] == "insufficient_data"
    assert overall["stability_score"] == 0.0


def test_walk_forward_positive_window_calculates_metrics(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        trade(f"train_{index}", base + timedelta(days=index), 1)
        for index in range(5)
    ]
    rows.extend(
        trade(f"test_{index}", base + timedelta(days=10 + index), 1)
        for index in range(5)
    )
    write_csv(tmp_path / "data" / "live_trading" / "trades.csv", rows)

    result = run_walk_forward_backtest(
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports",
        train_days=10,
        test_days=5,
        step_days=5,
        min_trades=5,
    )

    overall = rows_by_group(result)[("OVERALL", "ALL")]
    assert overall["train_trades"] == 5
    assert overall["test_trades"] == 5
    assert overall["train_winrate"] == 100.0
    assert overall["test_winrate"] == 100.0
    assert overall["train_total_r"] == 5.0
    assert overall["test_total_r"] == 5.0
    assert overall["overfit_warning"] == "stable_positive"


def test_walk_forward_negative_test_window_marks_overfit_warning(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        trade(f"train_{index}", base + timedelta(days=index), 1)
        for index in range(5)
    ]
    rows.extend(
        trade(f"test_{index}", base + timedelta(days=10 + index), -1)
        for index in range(5)
    )
    write_csv(tmp_path / "data" / "live_trading" / "trades.csv", rows)

    result = run_walk_forward_backtest(
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports",
        train_days=10,
        test_days=5,
        step_days=5,
        min_trades=5,
    )

    overall = rows_by_group(result)[("OVERALL", "ALL")]
    assert overall["test_total_r"] == -5.0
    assert overall["overfit_warning"] == "train_positive_test_negative"
    assert float(overall["stability_score"]) < 50


def test_walk_forward_writes_csv_outputs(tmp_path: Path) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        trade(f"train_{index}", base + timedelta(days=index), 1)
        for index in range(5)
    ]
    rows.extend(
        trade(f"test_{index}", base + timedelta(days=10 + index), 1)
        for index in range(5)
    )
    write_csv(tmp_path / "data" / "live_trading" / "trades.csv", rows)

    result = run_walk_forward_backtest(
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports",
        train_days=10,
        test_days=5,
        step_days=5,
        min_trades=5,
    )

    assert (tmp_path / "reports" / "walk_forward_backtest.csv").exists()
    assert (tmp_path / "reports" / "walk_forward_summary.csv").exists()
    assert "Walk-Forward Backtest" in format_walk_forward(result)
