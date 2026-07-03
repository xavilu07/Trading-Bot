from __future__ import annotations

import json

from scripts.analyze_edge_optimizer_shadow import analyze_events, load_shadow_events, write_reports


def test_analyzer_parses_optimizer_logs_and_writes_reports(tmp_path) -> None:
    log_file = tmp_path / "scheduler.log"
    report_json = tmp_path / "edge_optimizer_shadow_v1.json"
    report_md = tmp_path / "edge_optimizer_shadow_v1.md"
    events = [
        {
            "event": "edge_optimizer_shadow_decision",
            "symbol": "BTCUSDT",
            "direction": "long",
            "setup_type": "MAIN_SIGNAL",
            "current_decision": "REJECT",
            "current_score": 91,
            "optimizer_adjustment": 12,
            "optimizer_confidence": "HIGH",
            "matched_edges_count": 1,
            "matched_positive_edges": [_edge("positive", 12)],
            "matched_negative_edges": [],
            "top_edges": [_edge("positive", 12)],
            "hypothetical_score": 103,
            "hypothetical_bias": "STRONG_PRIORITIZE",
            "rejection_reasons": ["duplicate_signal_suppressed"],
            "context": {"session": "LONDON", "market_regime": "TRENDING", "entry_context": "PULLBACK"},
        },
        {
            "event": "edge_optimizer_shadow_decision",
            "symbol": "ETHUSDT",
            "direction": "short",
            "setup_type": "SECONDARY_SIGNAL",
            "current_decision": "SEND",
            "current_score": 75,
            "optimizer_adjustment": -8,
            "optimizer_confidence": "MEDIUM",
            "matched_edges_count": 1,
            "matched_positive_edges": [],
            "matched_negative_edges": [_edge("negative", -8)],
            "top_edges": [_edge("negative", -8)],
            "hypothetical_score": 67,
            "hypothetical_bias": "CAUTION",
            "rejection_reasons": [],
            "context": {"session": "ASIA", "market_regime": "RANGING", "entry_context": "BREAKOUT"},
        },
    ]
    log_file.write_text(
        "\n".join([json.dumps(events[0]), "2026-07-03 INFO " + json.dumps(events[1])]),
        encoding="utf-8",
    )

    parsed = load_shadow_events(log_file)
    analysis = analyze_events(parsed)
    paths = write_reports(analysis, report_json=report_json, report_md=report_md)

    assert len(parsed) == 2
    assert analysis["total_evaluations"] == 2
    assert analysis["bias_counts"]["STRONG_PRIORITIZE"] == 1
    assert analysis["bias_counts"]["CAUTION"] == 1
    assert len(analysis["high_score_rejected_optimizer_positive"]) == 1
    assert len(analysis["duplicate_signal_suppressed_optimizer_positive"]) == 1
    assert len(analysis["accepted_valid_optimizer_negative"]) == 1
    assert len(analysis["legacy_disagreements"]) == 2
    assert analysis["top_positive_edges"][0]["edge"] == "positive"
    assert analysis["top_negative_edges"][0]["edge"] == "negative"
    assert paths["json"].exists()
    assert paths["markdown"].exists()


def _edge(unique_id: str, weight: float) -> dict[str, object]:
    return {
        "unique_id": unique_id,
        "category": "priority_edges" if weight > 0 else "avoid_edges",
        "context": {"direction": "long"},
        "statistical_weight": weight,
        "confidence": "HIGH",
        "evidence_count": 50,
    }
