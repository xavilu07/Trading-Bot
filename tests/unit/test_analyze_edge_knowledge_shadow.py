from __future__ import annotations

import json

from scripts.analyze_edge_knowledge_shadow import analyze_events, load_shadow_events, write_reports


def test_analyzer_parses_fake_logs_and_writes_reports(tmp_path) -> None:
    log_file = tmp_path / "scheduler.log"
    report_json = tmp_path / "edge_knowledge_shadow_v1.json"
    report_md = tmp_path / "edge_knowledge_shadow_v1.md"
    events = [
        {
            "event": "edge_knowledge_shadow_decision",
            "symbol": "BTCUSDT",
            "direction": "long",
            "setup_type": "SECONDARY_SIGNAL",
            "current_decision": "REJECT",
            "current_score": 91,
            "ekb_bonus": 12,
            "ekb_confidence": "HIGH",
            "matched_edges_count": 1,
            "top_matched_edges": [
                {
                    "unique_id": "edge_positive",
                    "category": "priority_edges",
                    "context": {"direction": "long"},
                    "statistical_weight": 12,
                }
            ],
            "hypothetical_score": 103,
            "hypothetical_bias": "PRIORITIZE",
            "rejection_reasons": ["duplicate_signal_suppressed"],
            "context": {"session": "LONDON", "market_regime": "TRENDING"},
        },
        {
            "event": "edge_knowledge_shadow_decision",
            "symbol": "ETHUSDT",
            "direction": "short",
            "setup_type": "MAIN_SIGNAL",
            "current_decision": "SEND",
            "current_score": 62,
            "ekb_bonus": -10,
            "ekb_confidence": "MEDIUM",
            "matched_edges_count": 1,
            "top_matched_edges": [{"unique_id": "edge_negative", "statistical_weight": -10}],
            "hypothetical_score": 52,
            "hypothetical_bias": "AVOID",
            "rejection_reasons": [],
            "context": {"session": "ASIA", "market_regime": "RANGING"},
        },
    ]
    log_file.write_text(
        "\n".join(
            [
                json.dumps(events[0]),
                "2026-06-01 INFO " + json.dumps(events[1]),
                "not json",
            ]
        ),
        encoding="utf-8",
    )

    parsed = load_shadow_events(log_file)
    analysis = analyze_events(parsed)
    paths = write_reports(analysis, report_json=report_json, report_md=report_md)

    assert len(parsed) == 2
    assert analysis["total_shadow_evaluations"] == 2
    assert analysis["bias_counts"]["PRIORITIZE"] == 1
    assert analysis["bias_counts"]["AVOID"] == 1
    assert len(analysis["candidates_where_ekb_disagrees_with_legacy"]) == 2
    assert len(analysis["high_score_rejected_ekb_positive"]) == 1
    assert len(analysis["low_score_accepted_ekb_negative"]) == 1
    assert len(analysis["duplicate_signal_suppressed_ekb_positive"]) == 1
    assert paths["json"].exists()
    assert paths["markdown"].exists()
