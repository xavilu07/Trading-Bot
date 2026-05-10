from __future__ import annotations

import logging

from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.application.use_cases.paper_trading import build_paper_rejection_diagnostic
from trading_signals.application.use_cases.run_market_scan import (
    _candidate_rejected_payload,
    _log_candidate_rejected,
    _log_paper_candidate_rejected,
)
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from tests.unit.test_strategy_and_risk import build_snapshot


def test_candidate_rejected_logs_secondary_candidate(caplog) -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=65.0,
        distance=6.0,
        rsi=20.0,
        volume_ratio=2.0,
        break_of_structure="bearish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="XRPUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="no_trade",
        decision_trace=[],
        rejection_reasons=["distance_to_liquidity_extreme"],
        passed_filters=[],
        failed_filters=["distance_to_liquidity_extreme"],
        setup_score=65.0,
        confidence=0.65,
        created_at="2026-01-01T00:00:00+00:00",
    )

    with caplog.at_level(logging.INFO, logger="trading_signals"):
        payload = _candidate_rejected_payload(
            symbol="XRPUSDT",
            analysis=AnalysisResult("XRPUSDT", "1h", "4h", entry, higher),
            evaluation=evaluation,
        )
        _log_candidate_rejected(payload=payload)

    assert '"event": "CANDIDATE_REJECTED"' in caplog.text
    assert '"setup_type": "SECONDARY_SIGNAL"' in caplog.text
    assert '"direction": "short"' in caplog.text
    assert "distance_to_liquidity_extreme" in caplog.text


def test_paper_candidate_rejected_log_contains_validation_context(caplog) -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=30.0,
        distance=6.0,
        rsi=20.0,
        volume_ratio=2.0,
        break_of_structure="bearish_bos",
    )
    payload = build_paper_rejection_diagnostic(
        symbol="XRPUSDT",
        score=30.0,
        snapshot=entry,
        atr_min_threshold=0.002,
        max_spread_atr=1.8,
        rr_tp1=None,
        rr_tp2=None,
        rejection_reason="paper_rejected_below_low",
    )

    with caplog.at_level(logging.INFO, logger="trading_signals"):
        _log_paper_candidate_rejected(payload)

    assert '"event": "PAPER_CANDIDATE_REJECTED"' in caplog.text
    assert '"candidate_level_detected": "BELOW_LOW"' in caplog.text
    assert '"paper_trade_rejection_reason": "paper_rejected_below_low"' in caplog.text
    assert '"estimated_spread_atr"' in caplog.text
    assert '"market_movement_ok"' in caplog.text
