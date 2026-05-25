from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_strategy_opportunity_map import generate_strategy_opportunity_map


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def edge_row(group: str, *, labeled_rows: int, winrate: float, avg_result_r: float, total_result_r: float) -> dict[str, object]:
    return {
        "group_type": "entry_context",
        "group": group,
        "rows": labeled_rows,
        "labeled_rows": labeled_rows,
        "positive_labels": int(labeled_rows * winrate / 100),
        "negative_labels": labeled_rows - int(labeled_rows * winrate / 100),
        "winrate": winrate,
        "avg_result_r": avg_result_r,
        "total_result_r": total_result_r,
        "tp_hit_count": int(labeled_rows * winrate / 100),
        "sl_hit_count": labeled_rows - int(labeled_rows * winrate / 100),
        "unknown_count": 0,
        "confidence_level": "MEDIUM" if labeled_rows >= 10 else "LOW",
        "insufficient_data": labeled_rows < 10,
    }


def test_strategy_opportunity_map_classifies_promising(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(reports / "meta_dataset.csv", [{"signal_id": "sig_1"}])
    write_csv(
        reports / "meta_dataset_edge_analysis.csv",
        [edge_row("BREAKOUT", labeled_rows=12, winrate=66.7, avg_result_r=0.5, total_result_r=6.0)],
    )
    write_csv(reports / "meta_dataset_feature_summary.csv", [{"feature": "entry_context"}])

    result = generate_strategy_opportunity_map(reports_path=reports)

    assert result["rows"][0]["classification"] == "PROMISING"
    assert result["rows"][0]["recommendation"] == "mantener_observacion_prioritaria"


def test_strategy_opportunity_map_classifies_dangerous(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(reports / "meta_dataset.csv", [{"signal_id": "sig_1"}])
    write_csv(
        reports / "meta_dataset_edge_analysis.csv",
        [edge_row("PULLBACK", labeled_rows=12, winrate=25.0, avg_result_r=-0.6, total_result_r=-7.2)],
    )
    write_csv(reports / "meta_dataset_feature_summary.csv", [{"feature": "entry_context"}])

    result = generate_strategy_opportunity_map(reports_path=reports)

    assert result["rows"][0]["classification"] == "DANGEROUS"
    assert result["rows"][0]["next_action"] == "validar_si_debe_bloquear_publico"


def test_strategy_opportunity_map_classifies_low_data_avoid_public(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(reports / "meta_dataset.csv", [{"signal_id": "sig_1"}])
    write_csv(
        reports / "meta_dataset_edge_analysis.csv",
        [edge_row("CHOPPY_RANGE", labeled_rows=4, winrate=0.0, avg_result_r=-1.0, total_result_r=-4.0)],
    )
    write_csv(reports / "meta_dataset_feature_summary.csv", [{"feature": "entry_context"}])

    result = generate_strategy_opportunity_map(reports_path=reports)

    assert result["rows"][0]["classification"] == "AVOID_PUBLIC"
    assert result["rows"][0]["confidence_level"] == "LOW"
    assert result["rows"][0]["recommendation"] == "evitar_publico_temporalmente"


def test_strategy_opportunity_map_writes_csv_and_summary(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    write_csv(reports / "meta_dataset.csv", [{"signal_id": "sig_1"}])
    write_csv(
        reports / "meta_dataset_edge_analysis.csv",
        [edge_row("BREAKOUT", labeled_rows=5, winrate=40.0, avg_result_r=0.0, total_result_r=0.0)],
    )
    write_csv(reports / "meta_dataset_feature_summary.csv", [{"feature": "entry_context"}])

    result = generate_strategy_opportunity_map(reports_path=reports)

    assert Path(result["csv_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert "Strategy Opportunity Map" in Path(result["summary_path"]).read_text(encoding="utf-8")
