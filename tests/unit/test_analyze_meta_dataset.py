from __future__ import annotations

import csv
from pathlib import Path

from scripts.analyze_meta_dataset import analyze_meta_dataset, format_analysis


def write_meta_dataset(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def row(
    idx: int,
    *,
    label: str,
    result_r: float | str,
    entry_context: str = "BREAKOUT",
    market_regime: str = "TRENDING",
    has_against_htf: bool = False,
) -> dict[str, object]:
    return {
        "signal_id": f"sig_{idx}",
        "timestamp": f"2026-05-24T10:{idx:02d}:00+00:00",
        "symbol": "BTCUSDT",
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": market_regime,
        "session": "LONDON",
        "entry_context": entry_context,
        "trade_location": "mid_range",
        "label": label,
        "result_r": result_r,
        "has_against_htf": str(has_against_htf),
        "has_low_volume": "False",
        "has_dirty_sideways_market": "False",
        "has_market_structure_range_penalty": "False",
        "has_timeframe_alignment_penalty": "False",
        "has_secondary_confluence_bonus": "False",
    }


def test_analyze_meta_dataset_detects_negative_context(tmp_path: Path) -> None:
    rows = [row(i, label="0", result_r=-1, entry_context="PULLBACK", market_regime="RANGING") for i in range(10)]
    rows.extend(row(20 + i, label="1", result_r=1, entry_context="BREAKOUT", market_regime="TRENDING") for i in range(10))
    write_meta_dataset(tmp_path / "reports" / "meta_dataset.csv", rows)

    result = analyze_meta_dataset(reports_path=tmp_path / "reports")

    pullback = next(item for item in result["edge_rows"] if item["group_type"] == "entry_context" and item["group"] == "PULLBACK")
    assert pullback["labeled_rows"] == 10
    assert pullback["winrate"] == 0.0
    assert pullback["avg_result_r"] == -1.0
    assert pullback["insufficient_data"] is False


def test_analyze_meta_dataset_marks_insufficient_data_for_few_labels(tmp_path: Path) -> None:
    write_meta_dataset(
        tmp_path / "reports" / "meta_dataset.csv",
        [row(i, label="0", result_r=-1, has_against_htf=True) for i in range(3)],
    )

    result = analyze_meta_dataset(reports_path=tmp_path / "reports")

    against_htf = next(item for item in result["edge_rows"] if item["group_type"] == "has_against_htf" and item["group"] == "True")
    assert against_htf["labeled_rows"] == 3
    assert against_htf["confidence_level"] == "LOW"
    assert against_htf["insufficient_data"] is True


def test_analyze_meta_dataset_writes_csv_outputs(tmp_path: Path) -> None:
    write_meta_dataset(
        tmp_path / "reports" / "meta_dataset.csv",
        [row(i, label="1", result_r=1) for i in range(10)],
    )

    result = analyze_meta_dataset(reports_path=tmp_path / "reports")

    assert Path(result["edge_csv_path"]).exists()
    assert Path(result["feature_csv_path"]).exists()
    assert "Meta Dataset Edge Analysis" in format_analysis(result["summary"])


def test_analyze_meta_dataset_handles_unknown_labels(tmp_path: Path) -> None:
    write_meta_dataset(
        tmp_path / "reports" / "meta_dataset.csv",
        [
            row(1, label="", result_r=""),
            row(2, label="UNKNOWN", result_r=""),
            row(3, label="1", result_r=1),
        ],
    )

    result = analyze_meta_dataset(reports_path=tmp_path / "reports")

    direction = next(item for item in result["edge_rows"] if item["group_type"] == "direction" and item["group"] == "long")
    assert direction["rows"] == 3
    assert direction["labeled_rows"] == 1
    assert direction["unknown_count"] == 2
