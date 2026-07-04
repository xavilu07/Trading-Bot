from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.simulator import (
    BANNED_FILTER_FEATURES,
    build_filter_conditions,
    matches_condition,
    run_strategy_simulator,
    simulate_exclusion,
)


REPORTS = {
    "overview",
    "single_filters",
    "double_filters",
    "triple_filters",
    "best_configs",
    "worst_configs",
    "recommendations",
}


def test_build_conditions_uses_only_pre_trade_features(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=20, negative=20)
    rows = load_research_dataset(tmp_path / "data")["rows"]

    conditions = build_filter_conditions(rows, min_evidence=5, max_conditions=100)

    assert conditions
    assert not {condition["feature"] for condition in conditions} & BANNED_FILTER_FEATURES
    assert any(condition["label"] == "exclude session=NEW_YORK" for condition in conditions)
    assert not any(condition["label"] == "exclude strategy=liquidity_sweep_mtf_v1" for condition in conditions)
    assert not any(condition["label"] == "exclude rr_valid=True" for condition in conditions)


def test_multiple_sessions_generate_session_conditions(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=20, negative=20)
    rows = load_research_dataset(tmp_path / "data")["rows"]

    conditions = build_filter_conditions(rows, min_evidence=5, max_conditions=100)
    labels = {condition["label"] for condition in conditions}

    assert "exclude session=LONDON" in labels
    assert "exclude session=NEW_YORK" in labels


def test_simulate_exclusion_improves_when_removing_toxic_context(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=20, negative=20)
    rows = load_research_dataset(tmp_path / "data")["rows"]
    baseline = run_strategy_simulator(
        data_path=tmp_path / "data",
        reports_path=tmp_path / "reports" / "strategy_simulator",
        min_evidence=5,
    )["overview"]["baseline"]

    result = simulate_exclusion(
        rows,
        baseline,
        [{"feature": "session", "operator": "==", "value": "NEW_YORK", "label": "exclude session=NEW_YORK", "evidence": 20}],
    )

    assert result["trades_eliminated"] == 20
    assert result["profit_factor"] > baseline["profit_factor"]
    assert result["delta_total_r"] > 0


def test_score_threshold_condition_matches_only_pre_trade_score() -> None:
    condition = {"feature": "score", "operator": "<", "value": 70}

    assert matches_condition({"score": 69, "result_r": 2.0}, condition)
    assert not matches_condition({"score": 90, "result_r": -1.0}, condition)
    assert not matches_condition({"result_r": -1.0}, {"feature": "result_r", "operator": "<", "value": 0})


def test_run_strategy_simulator_generates_all_reports(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=25, negative=25, open_rows=2)
    reports_path = tmp_path / "reports" / "strategy_simulator"

    result = run_strategy_simulator(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        max_conditions=30,
    )

    assert result["overview"]["baseline"]["trades"] == 52
    assert result["overview"]["condition_debug"]["total_candidate_conditions_before_filter"] > 0
    assert result["overview"]["condition_debug"]["total_candidate_conditions_after_filter"] > 0
    assert result["overview"]["condition_debug"]["skipped_constant_features"]
    for report in REPORTS:
        json_path = reports_path / f"{report}.json"
        md_path = reports_path / f"{report}.md"
        assert json_path.exists(), report
        assert md_path.exists(), report
        json.loads(json_path.read_text(encoding="utf-8"))


def test_simulator_outputs_recommendations_and_best_configs(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=25, negative=25)
    reports_path = tmp_path / "reports" / "strategy_simulator"

    run_strategy_simulator(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        max_conditions=30,
    )

    recommendations = json.loads((reports_path / "recommendations.json").read_text(encoding="utf-8"))
    best_configs = json.loads((reports_path / "best_configs.json").read_text(encoding="utf-8"))
    single_filters = json.loads((reports_path / "single_filters.json").read_text(encoding="utf-8"))

    assert recommendations["recommendations"]
    assert best_configs["configs"]
    assert any("exclude session=NEW_YORK" in item["conditions"] for item in single_filters["simulations"])


def test_max_conditions_two_generates_single_and_double_but_not_triple(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=25, negative=25)
    reports_path = tmp_path / "reports" / "strategy_simulator"

    run_strategy_simulator(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        max_conditions=2,
    )

    single_filters = json.loads((reports_path / "single_filters.json").read_text(encoding="utf-8"))
    double_filters = json.loads((reports_path / "double_filters.json").read_text(encoding="utf-8"))
    triple_filters = json.loads((reports_path / "triple_filters.json").read_text(encoding="utf-8"))

    assert single_filters["simulations"]
    assert double_filters["simulations"]
    assert triple_filters["simulations"] == []


def _write_fixture(tmp_path: Path, *, positive: int, negative: int, open_rows: int = 0) -> None:
    path = tmp_path / "data" / "paper_trading" / "trades.csv"
    path.parent.mkdir(parents=True)
    fieldnames = [
        "trade_id",
        "symbol",
        "direction",
        "setup_type",
        "score",
        "risk_reward_tp2",
        "opened_at",
        "closed_at",
        "candles_held",
        "status",
        "result_r",
        "volume_ratio",
        "rsi",
        "trend_1h",
        "trend_4h",
        "break_of_structure",
        "liquidity_sweep",
        "directional_distance_to_liquidity_atr",
        "market_regime",
        "session",
        "entry_context",
        "trade_location",
        "rr_valid",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(positive):
            writer.writerow(
                {
                    "trade_id": f"pos-{idx}",
                    "symbol": "ETHUSDT",
                    "direction": "short",
                    "setup_type": "SECONDARY_SIGNAL",
                    "score": "92",
                    "risk_reward_tp2": "2.5",
                    "opened_at": "2026-06-01T10:00:00Z",
                    "closed_at": "2026-06-01T12:00:00Z",
                    "candles_held": "5",
                    "status": "tp2_hit",
                    "result_r": "1.2",
                    "volume_ratio": "1.5",
                    "rsi": "48",
                    "trend_1h": "bearish",
                    "trend_4h": "bearish",
                    "break_of_structure": "bearish_bos",
                    "liquidity_sweep": "bearish_sweep",
                    "directional_distance_to_liquidity_atr": "1.5",
                    "market_regime": "HIGH_VOLATILITY",
                    "session": "LONDON",
                    "entry_context": "PULLBACK",
                    "trade_location": "premium_zone",
                    "rr_valid": "True",
                }
            )
        for idx in range(negative):
            writer.writerow(
                {
                    "trade_id": f"neg-{idx}",
                    "symbol": "BTCUSDT",
                    "direction": "long",
                    "setup_type": "MAIN_SIGNAL",
                    "score": "58",
                    "risk_reward_tp2": "1.2",
                    "opened_at": "2026-06-02T14:00:00Z",
                    "closed_at": "2026-06-02T15:00:00Z",
                    "candles_held": "3",
                    "status": "sl_hit",
                    "result_r": "-1.0",
                    "volume_ratio": "0.7",
                    "rsi": "62",
                    "trend_1h": "bearish",
                    "trend_4h": "bearish",
                    "break_of_structure": "bullish_bos",
                    "liquidity_sweep": "bullish_sweep",
                    "directional_distance_to_liquidity_atr": "4.5",
                    "market_regime": "RANGING",
                    "session": "NEW_YORK",
                    "entry_context": "BREAKOUT",
                    "trade_location": "near_support",
                    "rr_valid": "True",
                }
            )
        for idx in range(open_rows):
            writer.writerow(
                {
                    "trade_id": f"open-{idx}",
                    "symbol": "SOLUSDT",
                    "direction": "long",
                    "setup_type": "MAIN_SIGNAL",
                    "score": "75",
                    "risk_reward_tp2": "2.0",
                    "opened_at": "2026-06-03T09:00:00Z",
                    "closed_at": "",
                    "candles_held": "",
                    "status": "open",
                    "result_r": "",
                    "volume_ratio": "1.0",
                    "rsi": "50",
                    "trend_1h": "bullish",
                    "trend_4h": "bullish",
                    "break_of_structure": "bullish_bos",
                    "liquidity_sweep": "",
                    "directional_distance_to_liquidity_atr": "2.5",
                    "market_regime": "TRENDING",
                    "session": "OVERLAP",
                    "entry_context": "EXHAUSTION",
                    "trade_location": "mid_range",
                    "rr_valid": "True",
                }
            )
