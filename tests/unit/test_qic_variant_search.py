from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.agents.committee import run_quantum_investment_council_v2
from trading_signals.agents.qic_variant_search import (
    apply_variant_to_proposal,
    generate_variant_conditions,
    run_qic_variant_search,
)


def test_extreme_proposal_generates_variants() -> None:
    variants = generate_variant_conditions(_extreme_conditions())

    variant_types = {variant["variant_type"] for variant in variants}

    assert "drop_to_single_condition" in variant_types
    assert "soften_single_threshold" in variant_types
    assert "soften_threshold_in_combo" in variant_types
    assert "conjunctive_filter" in variant_types


def test_variant_with_lower_reduction_is_selected(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _variant_rows())

    result = run_qic_variant_search(
        _extreme_proposal(),
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    selected = result["selected_variant"]
    assert result["status"] == "variant_found"
    assert selected["valid"] is True
    assert selected["trade_reduction_pct"] <= 60
    assert selected["profit_factor"] >= 1.05
    assert selected["total_r"] > 0
    assert (tmp_path / "reports" / "qic" / "variant_search.json").exists()
    assert (tmp_path / "reports" / "qic" / "variant_search.md").exists()


def test_no_valid_variant_requires_manual_research(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _no_variant_rows())

    result = run_qic_variant_search(
        _extreme_proposal(),
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )
    updated = apply_variant_to_proposal(_extreme_proposal(), result)

    assert result["status"] == "no_valid_variant"
    assert result["selected_variant"] is None
    assert updated["action"] == "REQUIRES_MANUAL_RESEARCH"
    assert "no_profitable_variant_found" in updated["risk_objections"]


def test_pf_below_1_05_is_invalid_even_if_baseline_improves(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _weak_improvement_rows())

    result = run_qic_variant_search(
        _extreme_proposal(),
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    assert result["status"] == "no_valid_variant"
    assert any("profit_factor_below_1_05" in variant["invalid_reason"] for variant in result["variants"])


def test_negative_total_r_variant_is_invalid(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _negative_total_r_rows())

    result = run_qic_variant_search(
        _extreme_proposal(),
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    assert result["status"] == "no_valid_variant"
    assert any("total_r_not_positive" in variant["invalid_reason"] for variant in result["variants"])


def test_variant_report_includes_invalid_reason(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _weak_improvement_rows())

    run_qic_variant_search(
        _extreme_proposal(),
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    report = (tmp_path / "reports" / "qic" / "variant_search.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "reports" / "qic" / "variant_search.json").read_text(encoding="utf-8"))
    assert "invalid_reason" in report
    assert any(variant["invalid_reason"] for variant in payload["variants"])


def test_bucket_value_less_than_1atr_does_not_crash(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _variant_rows())
    proposal = _extreme_proposal()
    proposal["context"] = {"conditions": ["exclude liquidity_distance_bucket=<1atr"]}

    result = run_qic_variant_search(
        proposal,
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    assert result["status"] in {"variant_found", "no_valid_variant"}
    assert json.loads((tmp_path / "reports" / "qic" / "variant_search.json").read_text(encoding="utf-8"))


def test_bucket_threshold_2_4atr_is_marked_non_numeric_without_crashing(tmp_path: Path) -> None:
    _write_trade_rows(tmp_path / "data", _variant_rows())
    proposal = _extreme_proposal()
    proposal["context"] = {
        "conditions": ["exclude liquidity_distance_bucket>=2-4atr"],
        "condition_details": [
            {
                "feature": "liquidity_distance_bucket",
                "operator": ">=",
                "value": "2-4atr",
                "label": "exclude liquidity_distance_bucket>=2-4atr",
            }
        ],
    }

    result = run_qic_variant_search(
        proposal,
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "qic",
        min_evidence=20,
    )

    assert result["status"] == "no_valid_variant"
    assert any("non_numeric_threshold" in variant["invalid_reason"] for variant in result["variants"])


def test_qic_uses_variant_as_final_telegram_proposal(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path)
    _write_trade_rows(tmp_path / "data", _variant_rows())

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        dry_run=True,
    )

    proposal = result["single_proposal"]
    assert proposal["action"] == "PROPOSE_VARIANT"
    assert proposal["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert proposal["trade_reduction_pct"] <= 60
    assert "variant_search" in proposal["context"]
    assert result["telegram_results"][0]["status"] == "dry_run"
    assert "CIO variant proposal" in result["telegram_results"][0]["payload"]["text"]
    assert json.loads((tmp_path / "reports" / "qic" / "variant_search.json").read_text())


def test_top_extreme_without_variant_falls_through_to_second_candidate(tmp_path: Path) -> None:
    _write_qic_reports_with_two_candidates(tmp_path)
    _write_trade_rows(tmp_path / "data", _no_variant_rows())

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        dry_run=True,
    )

    proposal = result["single_proposal"]
    ranking = json.loads((tmp_path / "reports" / "qic" / "hypothesis_ranking.json").read_text(encoding="utf-8"))
    assert proposal["action"] == "PROPOSE_IMPLEMENTATION"
    assert proposal["context"]["conditions"] == ["exclude htf_alignment=against"]
    assert ranking["candidates"][0]["status"] == "discarded"
    assert ranking["candidates"][0]["discard_reason"] == "no_valid_variant_found"
    assert ranking["selected_rank"] == 2
    assert result["telegram_results"][0]["status"] == "dry_run"
    assert "exclude htf_alignment=against" in result["telegram_results"][0]["payload"]["text"]


def test_non_numeric_bucket_hypothesis_falls_through_to_next_candidate(tmp_path: Path) -> None:
    _write_qic_reports_with_bucket_candidate_then_valid_second(tmp_path)
    _write_trade_rows(tmp_path / "data", _variant_rows())

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=False,
    )

    ranking = json.loads((tmp_path / "reports" / "qic" / "hypothesis_ranking.json").read_text(encoding="utf-8"))
    assert result["single_proposal"]["action"] == "PROPOSE_IMPLEMENTATION"
    assert ranking["candidates"][0]["discard_reason"] == "no_valid_variant_found"
    variant_report = json.loads((tmp_path / "reports" / "qic" / "variant_search.json").read_text(encoding="utf-8"))
    assert any("non_numeric_threshold" in variant["invalid_reason"] for variant in variant_report["variants"])


def test_moderate_candidate_can_beat_extreme_high_pf_candidate(tmp_path: Path) -> None:
    _write_qic_reports_moderate_pool(tmp_path)
    _write_trade_rows(tmp_path / "data", _variant_rows())

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=False,
    )

    proposal = result["single_proposal"]
    ranking = json.loads((tmp_path / "reports" / "qic" / "hypothesis_ranking.json").read_text(encoding="utf-8"))
    assert proposal["action"] == "PROPOSE_IMPLEMENTATION"
    assert proposal["expected_pf"] == 1.13
    assert proposal["trade_reduction_pct"] == 49.0
    assert proposal["context"]["source"] == "single_filter"
    assert ranking["candidates"][0]["source"] == "single_filter"
    assert ranking["candidates"][0]["composite_score"] > ranking["candidates"][1]["composite_score"]


def test_hypothesis_ranking_report_includes_source_and_composite_score(tmp_path: Path) -> None:
    _write_qic_reports_moderate_pool(tmp_path)
    _write_trade_rows(tmp_path / "data", _variant_rows())

    run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=False,
    )

    report = (tmp_path / "reports" / "qic" / "hypothesis_ranking.md").read_text(encoding="utf-8")
    assert "source" in report
    assert "composite_score" in report


def test_all_invalid_candidates_emit_no_actionable_summary(tmp_path: Path) -> None:
    _write_qic_reports_all_extreme(tmp_path)
    _write_trade_rows(tmp_path / "data", _no_variant_rows())

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        dry_run=True,
    )

    ranking = json.loads((tmp_path / "reports" / "qic" / "hypothesis_ranking.json").read_text(encoding="utf-8"))
    assert result["proposal_count"] == 0
    assert result["single_proposal"] is None
    assert ranking["final_action"] == "NO_ACTIONABLE_PROPOSAL"
    assert all(item["status"] == "discarded" for item in ranking["candidates"])
    assert result["telegram_results"][0]["status"] == "dry_run"
    assert "No actionable proposal" in result["telegram_results"][0]["payload"]["text"]


def _extreme_conditions() -> list[dict[str, object]]:
    return [
        {"feature": "volume_ratio", "operator": ">=", "value": 1.2, "label": "exclude volume_ratio>=1.2"},
        {"feature": "rsi", "operator": ">=", "value": 55, "label": "exclude rsi>=55"},
    ]


def _extreme_proposal() -> dict[str, object]:
    return {
        "id": "cio_extreme",
        "title": "CIO variant search required: exclude volume_ratio>=1.2, exclude rsi>=55",
        "action": "REQUIRES_VARIANT_SEARCH",
        "risk_level": "EXTREME",
        "trade_reduction_pct": 70.0,
        "risk_objections": ["extreme_trade_reduction"],
        "context": {
            "conditions": ["exclude volume_ratio>=1.2", "exclude rsi>=55"],
            "condition_details": _extreme_conditions(),
        },
    }


def _variant_rows() -> list[dict[str, object]]:
    rows = []
    rows.extend(_rows(40, result_r=-1.0, volume_ratio=1.3, rsi=50))
    rows.extend(_rows(20, result_r=-1.0, volume_ratio=1.6, rsi=50))
    rows.extend(_rows(10, result_r=-1.0, volume_ratio=1.0, rsi=58))
    rows.extend(_rows(30, result_r=1.0, volume_ratio=1.0, rsi=45))
    return rows


def _no_variant_rows() -> list[dict[str, object]]:
    rows = []
    rows.extend(_rows(70, result_r=1.0, volume_ratio=1.4, rsi=60))
    rows.extend(_rows(30, result_r=-1.0, volume_ratio=1.0, rsi=45))
    return rows


def _weak_improvement_rows() -> list[dict[str, object]]:
    rows = []
    rows.extend(_rows(25, result_r=-1.0, volume_ratio=1.3, rsi=50))
    rows.extend(_rows(25, result_r=-0.5, volume_ratio=1.0, rsi=58))
    rows.extend(_rows(25, result_r=0.4, volume_ratio=1.0, rsi=45))
    rows.extend(_rows(25, result_r=-1.0, volume_ratio=1.0, rsi=45))
    return rows


def _negative_total_r_rows() -> list[dict[str, object]]:
    rows = []
    rows.extend(_rows(30, result_r=-1.0, volume_ratio=1.3, rsi=50))
    rows.extend(_rows(20, result_r=-0.25, volume_ratio=1.0, rsi=58))
    rows.extend(_rows(50, result_r=0.1, volume_ratio=1.0, rsi=45))
    return rows


def _rows(count: int, *, result_r: float, volume_ratio: float, rsi: float) -> list[dict[str, object]]:
    return [
        {
            "symbol": "BTCUSDT",
            "direction": "long",
            "setup_type": "MAIN_SIGNAL",
            "session": "LONDON",
            "market_regime": "TRENDING",
            "entry_context": "BREAKOUT",
            "trade_location": "mid_range",
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "result_r": result_r,
            "status": "tp1_hit" if result_r > 0 else "sl_hit",
        }
        for _ in range(count)
    ]


def _write_trade_rows(data_path: Path, rows: list[dict[str, object]]) -> None:
    trades_path = data_path / "paper_trading" / "trades.csv"
    trades_path.parent.mkdir(parents=True)
    with trades_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_qic_reports(tmp_path: Path) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    simulation = {
        "simulation_type": "exclude",
        "conditions": ["exclude volume_ratio>=1.2", "exclude rsi>=55"],
        "condition_details": _extreme_conditions(),
        "trades_eliminated": 70,
        "remaining_closed": 30,
        "winrate": 100.0,
        "profit_factor": 10.0,
        "total_r": 30.0,
        "delta_total_r": 70.0,
        "confidence": "LOW",
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": [simulation]}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": [simulation]}), encoding="utf-8")
    (simulator / "overview.json").write_text(json.dumps({"baseline": {"closed": 100}}), encoding="utf-8")
    historical = tmp_path / "reports" / "historical_intelligence"
    historical.mkdir(parents=True)
    (historical / "negative_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    (historical / "positive_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    quant = tmp_path / "reports" / "quant_research"
    quant.mkdir(parents=True)
    (quant / "feature_importance.json").write_text(json.dumps({"features": []}), encoding="utf-8")


def _write_qic_reports_with_two_candidates(tmp_path: Path) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    extreme = {
        "simulation_type": "exclude",
        "conditions": ["exclude volume_ratio>=1.2", "exclude rsi>=55"],
        "condition_details": _extreme_conditions(),
        "trades_eliminated": 70,
        "remaining_closed": 30,
        "profit_factor": 10.0,
        "total_r": 30.0,
        "delta_total_r": 70.0,
        "confidence": "LOW",
    }
    second = {
        "simulation_type": "exclude",
        "conditions": ["exclude htf_alignment=against"],
        "condition_details": [{"feature": "htf_alignment", "operator": "==", "value": "against", "label": "exclude htf_alignment=against"}],
        "trades_eliminated": 20,
        "remaining_closed": 80,
        "profit_factor": 1.25,
        "total_r": 12.0,
        "delta_total_r": 12.0,
        "confidence": "LOW",
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": [second]}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": [extreme]}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": []}), encoding="utf-8")
    (simulator / "overview.json").write_text(json.dumps({"baseline": {"closed": 100}}), encoding="utf-8")
    _write_empty_support_reports(tmp_path)


def _write_qic_reports_all_extreme(tmp_path: Path) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    extreme = {
        "simulation_type": "exclude",
        "conditions": ["exclude volume_ratio>=1.2", "exclude rsi>=55"],
        "condition_details": _extreme_conditions(),
        "trades_eliminated": 70,
        "remaining_closed": 30,
        "profit_factor": 10.0,
        "total_r": 30.0,
        "delta_total_r": 70.0,
        "confidence": "LOW",
    }
    other_extreme = {
        "simulation_type": "exclude",
        "conditions": ["exclude score>=90"],
        "condition_details": [{"feature": "score", "operator": ">=", "value": 90, "label": "exclude score>=90"}],
        "trades_eliminated": 65,
        "remaining_closed": 35,
        "profit_factor": 2.0,
        "total_r": 10.0,
        "delta_total_r": 20.0,
        "confidence": "LOW",
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": [other_extreme]}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": [extreme]}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": []}), encoding="utf-8")
    (simulator / "overview.json").write_text(json.dumps({"baseline": {"closed": 100}}), encoding="utf-8")
    _write_empty_support_reports(tmp_path)


def _write_qic_reports_with_bucket_candidate_then_valid_second(tmp_path: Path) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    bucket_extreme = {
        "simulation_type": "exclude",
        "conditions": ["exclude liquidity_distance_bucket>=2-4atr"],
        "condition_details": [
            {
                "feature": "liquidity_distance_bucket",
                "operator": ">=",
                "value": "2-4atr",
                "label": "exclude liquidity_distance_bucket>=2-4atr",
            }
        ],
        "trades_eliminated": 70,
        "remaining_closed": 30,
        "profit_factor": 10.0,
        "total_r": 30.0,
        "delta_total_r": 70.0,
        "confidence": "LOW",
    }
    second = {
        "simulation_type": "exclude",
        "conditions": ["exclude htf_alignment=against"],
        "condition_details": [{"feature": "htf_alignment", "operator": "==", "value": "against", "label": "exclude htf_alignment=against"}],
        "trades_eliminated": 20,
        "remaining_closed": 80,
        "profit_factor": 1.25,
        "total_r": 12.0,
        "delta_total_r": 12.0,
        "confidence": "LOW",
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": [second]}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": [bucket_extreme]}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": []}), encoding="utf-8")
    (simulator / "overview.json").write_text(json.dumps({"baseline": {"closed": 100}}), encoding="utf-8")
    _write_empty_support_reports(tmp_path)


def _write_qic_reports_moderate_pool(tmp_path: Path) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    extreme = {
        "simulation_type": "exclude",
        "conditions": ["exclude volume_ratio>=1.2", "exclude rsi>=55"],
        "condition_details": _extreme_conditions(),
        "trades_eliminated": 900,
        "remaining_closed": 100,
        "profit_factor": 2.0,
        "total_r": 80.0,
        "delta_pf": 1.0,
        "delta_total_r": 180.0,
        "drawdown": -80.0,
        "confidence": "LOW",
    }
    moderate = {
        "simulation_type": "exclude",
        "conditions": ["exclude htf_alignment=against"],
        "condition_details": [{"feature": "htf_alignment", "operator": "==", "value": "against", "label": "exclude htf_alignment=against"}],
        "trades_eliminated": 490,
        "remaining_closed": 510,
        "profit_factor": 1.13,
        "total_r": 20.0,
        "delta_pf": 0.13,
        "delta_total_r": 120.0,
        "drawdown": -60.0,
        "confidence": "LOW",
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": [moderate]}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": [extreme]}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": []}), encoding="utf-8")
    (simulator / "recommendations.json").write_text(json.dumps({"recommendations": []}), encoding="utf-8")
    (simulator / "overview.json").write_text(
        json.dumps({"baseline": {"closed": 1000, "profit_factor": 1.0, "total_r": -100.0, "drawdown": -100.0}}),
        encoding="utf-8",
    )
    _write_empty_support_reports(tmp_path)


def _write_empty_support_reports(tmp_path: Path) -> None:
    historical = tmp_path / "reports" / "historical_intelligence"
    historical.mkdir(parents=True)
    (historical / "negative_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    (historical / "positive_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    quant = tmp_path / "reports" / "quant_research"
    quant.mkdir(parents=True)
    (quant / "feature_importance.json").write_text(json.dumps({"features": []}), encoding="utf-8")
