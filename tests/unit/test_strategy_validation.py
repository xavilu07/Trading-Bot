from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.strategy_validation import (
    load_strategy_validation_records,
    run_strategy_validation,
    write_strategy_validation_reports,
)


def test_strategy_validation_outputs_are_deterministic() -> None:
    records = [_record(index, result_r=1.0 if index % 2 == 0 else -1.0) for index in range(12)]

    first = run_strategy_validation(records, rolling_window=5, delay_candles=1)
    second = run_strategy_validation(records, rolling_window=5, delay_candles=1)

    assert first["validation_status"] == second["validation_status"]
    assert first["full_history_evaluation"] == second["full_history_evaluation"]
    assert first["matrix_rows"] == second["matrix_rows"]


def test_rolling_validation_correctness() -> None:
    records = [_record(index, result_r=1.0) for index in range(10)]

    result = run_strategy_validation(records, rolling_window=4, delay_candles=1)

    assert result["rolling_window_evaluation"]["windows"] >= 3
    assert result["rolling_window_evaluation"]["wr_stability"] == 0.0


def test_delayed_execution_skips_early_resolution() -> None:
    records = [
        _record(1, result_r=-1.0, candles_held=1),
        _record(2, result_r=2.0, candles_held=4),
    ]

    result = run_strategy_validation(records, rolling_window=2, delay_candles=1)

    assert result["delayed_execution_evaluation"]["input_records"] == 2
    assert result["delayed_execution_evaluation"]["skipped_early_resolution"] == 1
    assert result["delayed_execution_evaluation"]["delayed_records"] == 1


def test_no_future_candle_access_detects_open_before_candle_close() -> None:
    records = [
        {
            **_record(1, result_r=1.0),
            "dedupe_key": "BTCUSDT|long|x|v1|1h|2026-01-01T10:59:59+00:00",
            "opened_at": "2026-01-01T10:30:00+00:00",
        }
    ]

    result = run_strategy_validation(records, rolling_window=2, delay_candles=1)
    candle_check = _matrix(result, "candle_close_dependency_detection")

    assert candle_check["status"] in {"WARNING", "DANGEROUS"}
    assert float(candle_check["value"]) > 0


def test_strategy_validation_loads_data_and_writes_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "direction": "long",
                "status": "tp_hit",
                "result_r": "1",
                "opened_at": "2026-01-01T10:00:00+00:00",
                "closed_at": "2026-01-01T11:00:00+00:00",
            }
        ],
    )

    records = load_strategy_validation_records(data_path, reports_path)
    result = run_strategy_validation(records, rolling_window=1, delay_candles=1)
    paths = write_strategy_validation_reports(result, reports_path)

    assert len(records) == 1
    assert paths["json_path"].exists()
    assert paths["summary_path"].exists()
    assert paths["matrix_path"].exists()


def _record(index: int, *, result_r: float, candles_held: int = 3) -> dict[str, object]:
    return {
        "trade_id": f"trade_{index}",
        "dedupe_key": f"BTCUSDT|long|strategy|v1|1h|2026-01-01T{index % 24:02d}:59:59+00:00",
        "symbol": "BTCUSDT",
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "mid_range",
        "score": 80,
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": f"2026-01-01T{index % 24:02d}:00:00+00:00",
        "closed_at": f"2026-01-01T{(index + 1) % 24:02d}:00:00+00:00",
        "candles_held": candles_held,
    }


def _matrix(result: dict[str, object], validation: str) -> dict[str, object]:
    for row in result["matrix_rows"]:
        if row["validation"] == validation:
            return row
    raise AssertionError(f"missing validation {validation}")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
