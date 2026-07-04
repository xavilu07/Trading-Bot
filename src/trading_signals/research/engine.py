from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_signals.research.correlations import analyze_correlations
from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.discovery import discover_edges, feature_importance
from trading_signals.research.feature_extractor import extract_feature_names
from trading_signals.research.ranking import auto_clusters, outliers
from trading_signals.research.recommendations import build_recommendations
from trading_signals.research.statistics import compute_metrics
from trading_signals.research.strategy_v2_candidates import generate_strategy_v2_candidates


REPORTS = (
    "overview",
    "feature_importance",
    "feature_correlations",
    "edge_discovery",
    "clusters",
    "outliers",
    "strategy_v2_candidates",
    "recommendations",
)


def run_quant_research(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports") / "quant_research",
    min_evidence: int = 10,
    edge_min_evidence: int = 20,
) -> dict[str, Any]:
    dataset = load_research_dataset(data_path)
    rows = dataset["rows"]
    closed = [row for row in rows if row.get("result_r") is not None]
    features = extract_feature_names(rows)
    categorical = features["categorical"]
    overview = {
        "source": dataset["source"],
        "columns_detected": dataset["columns"],
        "features_detected": features,
        "auxiliary_sources": dataset["auxiliary_sources"],
        "metrics": compute_metrics(rows),
    }
    feature_importance_rows = feature_importance(closed, categorical, min_trades=min_evidence)
    correlations = analyze_correlations(closed, features)
    edges = discover_edges(closed, _edge_features(categorical), min_trades=edge_min_evidence)
    clusters = auto_clusters(closed, _edge_features(categorical), min_trades=min_evidence)
    outlier_report = outliers(closed)
    candidates = generate_strategy_v2_candidates(feature_importance_rows, edges)
    recommendations = build_recommendations(candidates, clusters)
    reports = {
        "overview": overview,
        "feature_importance": {"features": feature_importance_rows},
        "feature_correlations": correlations,
        "edge_discovery": edges,
        "clusters": clusters,
        "outliers": outlier_report,
        "strategy_v2_candidates": candidates,
        "recommendations": recommendations,
    }
    paths = write_reports(reports_path, reports)
    return {
        "reports_path": str(reports_path),
        "overview": overview,
        "paths": {name: {kind: str(path) for kind, path in report_paths.items()} for name, report_paths in paths.items()},
    }


def _edge_features(features: list[str]) -> list[str]:
    priority = [
        "symbol",
        "direction",
        "setup",
        "session",
        "market_regime",
        "location",
        "entry_zone",
        "score_bucket",
        "rr_bucket",
        "volume_ratio_bucket",
        "rsi_bucket",
        "liquidity_sweep",
        "htf_alignment",
        "ltf_alignment",
    ]
    available = [feature for feature in priority if feature in features]
    if len(available) >= 4:
        return available
    return features[:12]


def write_reports(reports_path: Path, reports: dict[str, Any]) -> dict[str, dict[str, Path]]:
    reports_path.mkdir(parents=True, exist_ok=True)
    output = {}
    for name in REPORTS:
        payload = reports.get(name, {})
        json_path = reports_path / f"{name}.json"
        md_path = reports_path / f"{name}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(to_markdown(name, payload), encoding="utf-8")
        output[name] = {"json": json_path, "markdown": md_path}
    return output


def to_markdown(name: str, payload: dict[str, Any]) -> str:
    lines = [f"# {name.replace('_', ' ').title()}", ""]
    if name == "overview":
        metrics = payload.get("metrics", {})
        lines.extend(_key_values(metrics))
        lines.append("")
        lines.append("## Data Sources")
        lines.extend(_key_values(payload.get("auxiliary_sources", {})))
    elif name == "feature_importance":
        lines.extend(_table(payload.get("features", [])))
    elif name == "feature_correlations":
        lines.append("## Positive")
        lines.extend(_table(payload.get("positive", [])[:50]))
        lines.append("")
        lines.append("## Negative")
        lines.extend(_table(payload.get("negative", [])[:50]))
    elif name == "edge_discovery":
        for section in ("top_by_pf", "top_by_expectancy", "top_by_total_r", "worst_by_total_r"):
            lines.append(f"## {section.replace('_', ' ').title()}")
            lines.extend(_table(payload.get(section, [])[:50]))
            lines.append("")
    elif name == "clusters":
        lines.append("## Positive Clusters")
        lines.extend(_table(payload.get("positive_clusters", [])[:50]))
        lines.append("")
        lines.append("## Negative Clusters")
        lines.extend(_table(payload.get("negative_clusters", [])[:50]))
    elif name == "outliers":
        lines.append("## Best Trades")
        lines.extend(_table(payload.get("best_trades", [])[:25]))
        lines.append("")
        lines.append("## Worst Trades")
        lines.extend(_table(payload.get("worst_trades", [])[:25]))
    elif name == "strategy_v2_candidates":
        lines.extend(_table(payload.get("candidates", [])[:100]))
    elif name == "recommendations":
        lines.extend(_table(payload.get("recommendations", [])[:100]))
    else:
        lines.append(json.dumps(payload, indent=2, sort_keys=True))
    return "\n".join(lines) + "\n"


def _key_values(payload: dict[str, Any]) -> list[str]:
    return [f"- {key}: {value}" for key, value in payload.items()]


def _table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No data."]
    columns = _columns(rows)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "feature",
        "value",
        "label",
        "cluster",
        "action",
        "recommendation",
        "context",
        "closed",
        "trades",
        "winrate",
        "profit_factor",
        "total_r",
        "avg_r",
        "expectancy",
        "confidence",
        "evidence",
        "expected_improvement",
        "expected_impact",
        "trades_affected",
        "correlation_score",
    ]
    available = {key for row in rows for key in row}
    return [key for key in preferred if key in available][:10]


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
