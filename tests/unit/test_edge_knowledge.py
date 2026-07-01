from __future__ import annotations

import json
from pathlib import Path

from trading_signals.intelligence.edge_knowledge import (
    build_edge_knowledge_from_report,
    calculate_statistical_weight,
    evaluate_context,
    load_edge_knowledge,
    write_edge_knowledge,
)


def test_build_edge_knowledge_extracts_priority_avoid_and_watch(tmp_path: Path) -> None:
    report_path = tmp_path / "performance_intelligence_report_v2.json"
    _write_report(report_path)

    knowledge = build_edge_knowledge_from_report(report_path, generated_at="2026-07-01T00:00:00+00:00")

    assert knowledge["summary"]["priority_edges"] == 1
    assert knowledge["summary"]["avoid_edges"] == 1
    assert knowledge["summary"]["watch_edges"] == 1
    priority = knowledge["priority_edges"][0]
    avoid = knowledge["avoid_edges"][0]
    assert priority["context"] == {"direction": "long", "session": "LONDON"}
    assert avoid["context"] == {"direction": "short"}
    assert priority["statistical_weight"] > 0
    assert avoid["statistical_weight"] < 0
    assert priority["evidence_count"] == 42
    assert priority["source_report"] == str(report_path)


def test_write_and_load_edge_knowledge(tmp_path: Path) -> None:
    report_path = tmp_path / "performance_intelligence_report_v2.json"
    output_path = tmp_path / "data" / "edge_knowledge" / "knowledge_v1.json"
    reports_path = tmp_path / "reports"
    _write_report(report_path)

    paths = write_edge_knowledge(report_path=report_path, output_path=output_path, reports_path=reports_path)
    loaded = load_edge_knowledge(output_path)

    assert paths["knowledge"].exists()
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert loaded["summary"]["total_edges"] == 3
    assert "Edge Knowledge Base V1" in paths["markdown"].read_text(encoding="utf-8")


def test_extracts_hints_recursively_from_groups_with_alias_fields(tmp_path: Path) -> None:
    report_path = tmp_path / "performance_intelligence_report_v2.json"
    report_path.write_text(
        json.dumps(
            {
                "groups": {
                    "single": [
                        {
                            "dimension": "direction + session",
                            "value": "short + LONDON",
                            "trades": 65,
                            "PF": 2.52,
                            "total_r": 30.9,
                            "avg_r": 0.47,
                            "winrate": 61.0,
                            "confidence": "HIGH",
                            "hint": "PRIORITIZE",
                        },
                        {
                            "dimension": "score_bucket",
                            "value": "90-100",
                            "closed_trades": 31,
                            "profit_factor": 0.42,
                            "totalR": -12.0,
                            "avgR": -0.38,
                            "winrate": 19.0,
                            "confidence": "HIGH",
                            "action": "AVOID",
                        },
                        {
                            "dimension": "trade_location",
                            "value": "near_support",
                            "sample_size": 18,
                            "profit_factor": 1.05,
                            "total_r": 0.8,
                            "avg_r": 0.04,
                            "winrate": 44.0,
                            "confidence": "MEDIUM",
                            "decision_hint": "WATCH",
                        },
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    knowledge = build_edge_knowledge_from_report(report_path)

    assert knowledge["summary"]["priority_edges"] == 1
    assert knowledge["summary"]["avoid_edges"] == 1
    assert knowledge["summary"]["watch_edges"] == 1
    assert knowledge["priority_edges"][0]["context"] == {"direction": "short", "session": "LONDON"}
    assert knowledge["priority_edges"][0]["evidence_count"] == 65
    assert knowledge["priority_edges"][0]["metrics"]["profit_factor"] == 2.52
    assert knowledge["avoid_edges"][0]["context"] == {"score_bucket": "90-100"}
    assert knowledge["avoid_edges"][0]["statistical_weight"] < 0


def test_evaluate_context_returns_bonus_and_matched_edges(tmp_path: Path) -> None:
    report_path = tmp_path / "performance_intelligence_report_v2.json"
    _write_report(report_path)
    knowledge = build_edge_knowledge_from_report(report_path)

    positive = evaluate_context({"direction": "long", "session": "LONDON", "symbol": "BTCUSDT"}, knowledge)
    negative = evaluate_context({"direction": "short", "session": "NY"}, knowledge)
    neutral = evaluate_context({"direction": "long", "session": "ASIA"}, knowledge)

    assert positive["bonus"] > 0
    assert len(positive["matched_edges"]) == 1
    assert positive["confidence"] == "HIGH"
    assert negative["bonus"] < 0
    assert len(negative["matched_edges"]) == 1
    assert neutral["bonus"] == 0
    assert neutral["matched_edges"] == []
    assert neutral["confidence"] == "LOW"


def test_statistical_weight_is_bounded_and_continuous() -> None:
    strong = calculate_statistical_weight(
        {"profit_factor": 2.0, "totalR": 20.0, "avgR": 0.5, "n": 100, "confidence": "HIGH"}
    )
    weak = calculate_statistical_weight(
        {"profit_factor": 0.4, "totalR": -20.0, "avgR": -0.5, "n": 100, "confidence": "HIGH"}
    )
    low_sample = calculate_statistical_weight(
        {"profit_factor": 2.0, "totalR": 20.0, "avgR": 0.5, "n": 5, "confidence": "LOW"}
    )

    assert 0 < strong <= 25
    assert -25 <= weak < 0
    assert 0 < low_sample < strong


def test_missing_knowledge_file_fails_neutral(tmp_path: Path) -> None:
    loaded = load_edge_knowledge(tmp_path / "missing.json")
    result = evaluate_context({"direction": "long"}, loaded)

    assert loaded["edges"] == []
    assert result == {"bonus": 0, "matched_edges": [], "confidence": "LOW"}


def _write_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "rankings": {
                    "prioritize": [
                        {
                            "dimension": "direction + session",
                            "value": "long + LONDON",
                            "n": 42,
                            "profit_factor": 1.8,
                            "totalR": 12.5,
                            "avgR": 0.29,
                            "winrate": 57.0,
                            "confidence": "HIGH",
                            "decision_hint": "PRIORITIZE",
                        }
                    ],
                    "avoid": [
                        {
                            "dimension": "direction",
                            "value": "short",
                            "n": 38,
                            "profit_factor": 0.5,
                            "totalR": -9.0,
                            "avgR": -0.24,
                            "winrate": 25.0,
                            "confidence": "HIGH",
                            "decision_hint": "AVOID",
                        }
                    ],
                    "best_edges": [],
                    "worst_edges": [],
                },
                "actionable_decisions": {
                    "watch": [
                        {
                            "dimension": "market_regime",
                            "value": "RANGING",
                            "n": 18,
                            "profit_factor": 1.05,
                            "totalR": 0.8,
                            "avgR": 0.04,
                            "winrate": 44.0,
                            "confidence": "MEDIUM",
                            "decision_hint": "WATCH",
                        }
                    ]
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
