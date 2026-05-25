from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


GROUP_DEFINITIONS: tuple[str | tuple[str, ...], ...] = (
    "symbol",
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    ("direction", "market_regime"),
    ("setup_type", "entry_context"),
    ("market_regime", "entry_context"),
    ("trade_location", "entry_context"),
    "has_against_htf",
    "has_low_volume",
    "has_dirty_sideways_market",
    "has_market_structure_range_penalty",
    "has_timeframe_alignment_penalty",
    "has_secondary_confluence_bonus",
)

EDGE_FIELDS = [
    "group_type",
    "group",
    "rows",
    "labeled_rows",
    "positive_labels",
    "negative_labels",
    "winrate",
    "avg_result_r",
    "total_result_r",
    "tp_hit_count",
    "sl_hit_count",
    "unknown_count",
    "confidence_level",
    "insufficient_data",
]

FEATURE_FIELDS = [
    "feature",
    "groups",
    "rows",
    "labeled_rows",
    "positive_labels",
    "negative_labels",
    "winrate",
    "avg_result_r",
    "total_result_r",
    "best_group",
    "best_avg_result_r",
    "worst_group",
    "worst_avg_result_r",
]

MIN_LABELED_ROWS = 10


def analyze_meta_dataset(*, reports_path: Path, min_labeled_rows: int = MIN_LABELED_ROWS) -> dict[str, Any]:
    dataset_path = reports_path / "meta_dataset.csv"
    rows = _read_csv(dataset_path)
    edge_rows = build_edge_analysis(rows, min_labeled_rows=min_labeled_rows)
    feature_rows = build_feature_summary(edge_rows)

    reports_path.mkdir(parents=True, exist_ok=True)
    edge_path = reports_path / "meta_dataset_edge_analysis.csv"
    feature_path = reports_path / "meta_dataset_feature_summary.csv"
    _write_csv(edge_path, edge_rows, EDGE_FIELDS)
    _write_csv(feature_path, feature_rows, FEATURE_FIELDS)
    return {
        "rows": rows,
        "edge_rows": edge_rows,
        "feature_rows": feature_rows,
        "edge_csv_path": edge_path,
        "feature_csv_path": feature_path,
        "summary": _summary(rows, edge_rows, min_labeled_rows=min_labeled_rows),
    }


def build_edge_analysis(rows: list[dict[str, str]], *, min_labeled_rows: int = MIN_LABELED_ROWS) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        for definition in GROUP_DEFINITIONS:
            group_type = _group_type(definition)
            group_value = _group_value(row, definition)
            if group_value:
                groups[(group_type, group_value)].append(row)

    output = []
    for (group_type, group), items in groups.items():
        output.append({"group_type": group_type, "group": group, **_metrics(items, min_labeled_rows=min_labeled_rows)})
    return sorted(output, key=lambda item: (str(item["group_type"]), float(item["avg_result_r"]), float(item["total_result_r"])))


def build_feature_summary(edge_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in edge_rows:
        grouped[str(row.get("group_type") or "")].append(row)

    summary_rows = []
    for feature, items in grouped.items():
        labeled = sum(int(item.get("labeled_rows") or 0) for item in items)
        positives = sum(int(item.get("positive_labels") or 0) for item in items)
        negatives = sum(int(item.get("negative_labels") or 0) for item in items)
        total_result = sum(float(item.get("total_result_r") or 0.0) for item in items)
        best_candidates = [item for item in items if str(item.get("insufficient_data")).lower() != "true"]
        best = max(best_candidates, key=lambda item: (float(item.get("avg_result_r") or 0.0), float(item.get("total_result_r") or 0.0)), default={})
        worst = min(items, key=lambda item: (float(item.get("avg_result_r") or 0.0), float(item.get("total_result_r") or 0.0)), default={})
        summary_rows.append(
            {
                "feature": feature,
                "groups": len(items),
                "rows": sum(int(item.get("rows") or 0) for item in items),
                "labeled_rows": labeled,
                "positive_labels": positives,
                "negative_labels": negatives,
                "winrate": round(positives / labeled * 100, 2) if labeled else 0.0,
                "avg_result_r": round(total_result / labeled, 4) if labeled else 0.0,
                "total_result_r": round(total_result, 4),
                "best_group": best.get("group", ""),
                "best_avg_result_r": best.get("avg_result_r", ""),
                "worst_group": worst.get("group", ""),
                "worst_avg_result_r": worst.get("avg_result_r", ""),
            }
        )
    return sorted(summary_rows, key=lambda item: str(item["feature"]))


def format_analysis(summary: dict[str, Any]) -> str:
    return (
        "🧠 Meta Dataset Edge Analysis\n"
        f"- Labeled rows: {summary.get('labeled_rows', 0)}\n"
        f"- TP/SL: {summary.get('tp_hit_count', 0)} / {summary.get('sl_hit_count', 0)}\n"
        f"- Best contexts: {_format_contexts(summary.get('best_contexts'))}\n"
        f"- Worst contexts: {_format_contexts(summary.get('worst_contexts'))}\n"
        f"- Strong negative rules candidates: {_format_contexts(summary.get('strong_negative_rule_candidates'))}"
    )


def _metrics(rows: list[dict[str, str]], *, min_labeled_rows: int) -> dict[str, Any]:
    labeled = [row for row in rows if str(row.get("label") or "").strip() in {"0", "1"}]
    positives = [row for row in labeled if str(row.get("label")) == "1"]
    negatives = [row for row in labeled if str(row.get("label")) == "0"]
    result_values = [_float(row.get("result_r")) for row in labeled if _float(row.get("result_r")) is not None]
    labeled_count = len(labeled)
    insufficient = labeled_count < min_labeled_rows
    return {
        "rows": len(rows),
        "labeled_rows": labeled_count,
        "positive_labels": len(positives),
        "negative_labels": len(negatives),
        "winrate": round(len(positives) / labeled_count * 100, 2) if labeled_count else 0.0,
        "avg_result_r": round(sum(result_values) / len(result_values), 4) if result_values else 0.0,
        "total_result_r": round(sum(result_values), 4),
        "tp_hit_count": len(positives),
        "sl_hit_count": len(negatives),
        "unknown_count": len(rows) - labeled_count,
        "confidence_level": _confidence_level(labeled_count),
        "insufficient_data": insufficient,
    }


def _summary(rows: list[dict[str, str]], edge_rows: list[dict[str, Any]], *, min_labeled_rows: int) -> dict[str, Any]:
    global_metrics = _metrics(rows, min_labeled_rows=min_labeled_rows)
    best = [
        row
        for row in sorted(edge_rows, key=lambda item: (float(item.get("avg_result_r") or 0.0), float(item.get("total_result_r") or 0.0)), reverse=True)
        if int(row.get("labeled_rows") or 0) >= min_labeled_rows
    ][:5]
    worst = sorted(edge_rows, key=lambda item: (float(item.get("avg_result_r") or 0.0), float(item.get("total_result_r") or 0.0)))[:5]
    strong_negative = [
        row
        for row in worst
        if int(row.get("labeled_rows") or 0) >= min_labeled_rows and float(row.get("avg_result_r") or 0.0) < 0
    ][:5]
    return {
        **global_metrics,
        "best_contexts": best,
        "worst_contexts": worst,
        "strong_negative_rule_candidates": strong_negative,
    }


def _confidence_level(labeled_rows: int) -> str:
    if labeled_rows >= 30:
        return "HIGH"
    if labeled_rows >= 10:
        return "MEDIUM"
    return "LOW"


def _group_type(definition: str | tuple[str, ...]) -> str:
    return definition if isinstance(definition, str) else "+".join(definition)


def _group_value(row: dict[str, str], definition: str | tuple[str, ...]) -> str:
    if isinstance(definition, str):
        return _normalize_value(row.get(definition))
    return "|".join(_normalize_value(row.get(field)) for field in definition)


def _normalize_value(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _format_contexts(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return "; ".join(
        f"{item.get('group_type')}={item.get('group')} avgR={item.get('avg_result_r')} n={item.get('labeled_rows')}"
        for item in value
        if isinstance(item, dict)
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="analyze-meta-dataset")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-labeled-rows", type=int, default=MIN_LABELED_ROWS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_meta_dataset(reports_path=Path(args.reports_path), min_labeled_rows=max(1, args.min_labeled_rows))
    print(format_analysis(result["summary"]))
    print(f"Edge analysis: {result['edge_csv_path']}")
    print(f"Feature summary: {result['feature_csv_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
