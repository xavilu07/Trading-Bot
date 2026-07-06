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
    assert selected["conditions"] == ["exclude rsi>=55"]
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
    assert "no_valid_variant_found" in updated["risk_objections"]


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
