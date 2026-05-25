from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Any


OUTPUT_FIELDS = [
    "dimension",
    "value",
    "classification",
    "labeled_rows",
    "winrate",
    "avg_result_r",
    "total_result_r",
    "confidence_level",
    "recommendation",
    "next_action",
]


def generate_strategy_opportunity_map(*, reports_path: Path) -> dict[str, Any]:
    meta_rows = _read_csv(reports_path / "meta_dataset.csv")
    edge_rows = _read_csv(reports_path / "meta_dataset_edge_analysis.csv")
    _read_csv(reports_path / "meta_dataset_feature_summary.csv")  # Optional input kept for completeness/future use.
    output_rows = [_opportunity_row(row) for row in edge_rows]
    output_rows = sorted(
        output_rows,
        key=lambda row: (
            _classification_rank(str(row["classification"])),
            -int(row.get("labeled_rows") or 0),
            float(row.get("avg_result_r") or 0.0),
        ),
    )

    reports_path.mkdir(parents=True, exist_ok=True)
    csv_path = reports_path / "strategy_opportunity_map.csv"
    summary_path = reports_path / "strategy_opportunity_summary.txt"
    _write_csv(csv_path, output_rows)
    summary = _summary(output_rows, meta_rows)
    summary_text = format_summary(summary)
    summary_path.write_text(summary_text + "\n", encoding="utf-8")
    return {
        "rows": output_rows,
        "summary": summary,
        "csv_path": csv_path,
        "summary_path": summary_path,
        "summary_text": summary_text,
    }


def format_summary(summary: dict[str, Any]) -> str:
    return (
        "🧭 Strategy Opportunity Map\n"
        f"- Promising contexts: {_format_items(summary.get('promising_contexts'))}\n"
        f"- Dangerous contexts: {_format_items(summary.get('dangerous_contexts'))}\n"
        f"- Avoid public candidates: {_format_items(summary.get('avoid_public_candidates'))}\n"
        f"- Needs more data: {summary.get('needs_more_data_count', 0)}\n"
        f"- Next recommended action: {summary.get('next_recommended_action', 'collect_more_labeled_data')}"
    )


def _opportunity_row(row: dict[str, str]) -> dict[str, Any]:
    labeled_rows = _int(row.get("labeled_rows"))
    winrate = _float(row.get("winrate")) or 0.0
    avg_result_r = _float(row.get("avg_result_r")) or 0.0
    total_result_r = _float(row.get("total_result_r")) or 0.0
    confidence = str(row.get("confidence_level") or _confidence_level(labeled_rows)).upper()
    classification = _classify(labeled_rows=labeled_rows, winrate=winrate, avg_result_r=avg_result_r)
    if classification in {"AVOID_PUBLIC", "NEEDS_MORE_DATA"} and labeled_rows < 10:
        confidence = "LOW"
    recommendation, next_action = _recommendation(classification, confidence)
    return {
        "dimension": row.get("group_type", ""),
        "value": row.get("group", ""),
        "classification": classification,
        "labeled_rows": labeled_rows,
        "winrate": round(winrate, 2),
        "avg_result_r": round(avg_result_r, 4),
        "total_result_r": round(total_result_r, 4),
        "confidence_level": confidence,
        "recommendation": recommendation,
        "next_action": next_action,
    }


def _classify(*, labeled_rows: int, winrate: float, avg_result_r: float) -> str:
    if labeled_rows >= 10 and avg_result_r > 0 and winrate > 50:
        return "PROMISING"
    if labeled_rows >= 10 and avg_result_r < 0 and winrate < 40:
        return "DANGEROUS"
    if avg_result_r < -0.2:
        return "AVOID_PUBLIC"
    if labeled_rows < 10:
        return "NEEDS_MORE_DATA"
    if abs(avg_result_r) <= 0.1:
        return "WATCHLIST"
    return "WATCHLIST"


def _recommendation(classification: str, confidence: str) -> tuple[str, str]:
    if classification == "PROMISING":
        return "mantener_observacion_prioritaria", "seguir_acumulando_muestra_antes_de_relajar"
    if classification == "DANGEROUS":
        return "evitar_publicacion_y_revisar_gate", "validar_si_debe_bloquear_publico"
    if classification == "AVOID_PUBLIC":
        return "evitar_publico_temporalmente", "recoger_mas_muestra_en_dev_paper"
    if classification == "NEEDS_MORE_DATA":
        return "no_tocar_estrategia", "recoger_mas_labels"
    return "monitorizar", "mantener_en_watchlist"


def _summary(rows: list[dict[str, Any]], meta_rows: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter(str(row.get("classification")) for row in rows)
    promising = _top(rows, "PROMISING", reverse=True)
    dangerous = _top(rows, "DANGEROUS", reverse=False)
    avoid_public = _top(rows, "AVOID_PUBLIC", reverse=False)
    return {
        "total_meta_rows": len(meta_rows),
        "classification_counts": dict(counts),
        "promising_contexts": promising,
        "dangerous_contexts": dangerous,
        "avoid_public_candidates": avoid_public,
        "needs_more_data_count": counts.get("NEEDS_MORE_DATA", 0),
        "next_recommended_action": _next_action(counts),
    }


def _top(rows: list[dict[str, Any]], classification: str, *, reverse: bool) -> list[dict[str, Any]]:
    candidates = [row for row in rows if row.get("classification") == classification]
    return sorted(candidates, key=lambda row: (float(row.get("avg_result_r") or 0.0), float(row.get("total_result_r") or 0.0)), reverse=reverse)[:5]


def _next_action(counts: Counter[str]) -> str:
    if counts.get("DANGEROUS", 0) or counts.get("AVOID_PUBLIC", 0):
        return "priorizar_revision_de_contextos_peligrosos_y_mantenerlos_fuera_del_publico"
    if counts.get("PROMISING", 0):
        return "seguir_observando_contextos_prometedores_sin_relajar_estrategia"
    return "recoger_mas_labels_antes_de_tocar_estrategia"


def _format_items(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return "; ".join(
        f"{item.get('dimension')}={item.get('value')} avgR={item.get('avg_result_r')} n={item.get('labeled_rows')}"
        for item in value
        if isinstance(item, dict)
    )


def _classification_rank(value: str) -> int:
    order = {
        "DANGEROUS": 0,
        "AVOID_PUBLIC": 1,
        "PROMISING": 2,
        "WATCHLIST": 3,
        "NEEDS_MORE_DATA": 4,
    }
    return order.get(value, 9)


def _confidence_level(labeled_rows: int) -> str:
    if labeled_rows >= 30:
        return "HIGH"
    if labeled_rows >= 10:
        return "MEDIUM"
    return "LOW"


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-strategy-opportunity-map")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_strategy_opportunity_map(reports_path=Path(args.reports_path))
    print(result["summary_text"])
    print(f"CSV: {result['csv_path']}")
    print(f"Summary: {result['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
