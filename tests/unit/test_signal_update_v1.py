from __future__ import annotations

from pathlib import Path

from trading_signals.application.use_cases.signal_lifecycle import SignalLifecycleDecision
from trading_signals.application.use_cases.signal_update_v1 import (
    UPDATE_INVALIDATION,
    UPDATE_NONE,
    UPDATE_REENTRY,
    UPDATE_STRENGTHENED,
    diagnose_signal_update_v1_skip,
    evaluate_signal_update_v1,
    write_signal_update_v1_design_report,
    write_signal_update_v1_shadow_report,
)
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal
from tests.unit.test_strategy_and_risk import build_snapshot


class FakeSignalRepo:
    def __init__(self, signals: list[dict[str, object]]) -> None:
        self.signals = signals

    def list_latest_signals(self, limit: int = 20) -> list[dict[str, object]]:
        return self.signals[:limit]


def _signal(*, dedupe_key: str = "BTC|long|new") -> TradeSignal:
    return TradeSignal(
        id="sig_new",
        scan_run_id="run",
        evaluation_id="eval",
        risk_plan_id="risk",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision="long",
        status="valid",
        dedupe_key=dedupe_key,
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        created_at="2026-01-01T01:00:00+00:00",
    )


def _evaluation(
    *,
    score: float = 100.0,
    passed_filters: list[str] | None = None,
    failed_filters: list[str] | None = None,
    rejection_reasons: list[str] | None = None,
) -> StrategyEvaluation:
    return StrategyEvaluation(
        id="eval",
        scan_run_id="run",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        decision="long",
        decision_trace=[],
        rejection_reasons=rejection_reasons or [],
        passed_filters=passed_filters if passed_filters is not None else ["directional_confluence"],
        failed_filters=failed_filters or [],
        setup_score=score,
        confidence=0.9,
        created_at="2026-01-01T01:00:00+00:00",
    )


def _risk(rr: float = 2.0) -> RiskPlan:
    return RiskPlan(
        id="risk",
        evaluation_id="eval",
        entry=100.0,
        stop_loss=99.0,
        take_profit=100.0 + rr,
        risk_reward=rr,
        risk_amount=10.0,
        position_size=1.0,
        sl_method="test",
        tp_method="test",
        created_at="2026-01-01T01:00:00+00:00",
    )


def _snapshot(*, dedupe_time: str = "2026-01-01T01:00:00+00:00", distance: float = 4.0, bos: str = "none"):
    snapshot = build_snapshot(
        scan_run_id="run",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=100.0,
        distance=distance,
        break_of_structure=bos,
    )
    snapshot.timestamp = dedupe_time
    return snapshot


def _active(*, score: float | None = 90.0, rr: float | None = 2.0, dedupe_key: str = "BTC|long|old") -> dict[str, object]:
    item: dict[str, object] = {
        "id": "sig_active",
        "symbol": "BTCUSDT",
        "decision": "long",
        "published_at": "2026-01-01T00:00:00+00:00",
        "dedupe_key": dedupe_key,
    }
    if score is not None:
        item["score"] = score
    if rr is not None:
        item["risk_reward"] = rr
    return item


def test_detects_strengthened_signal_when_score_not_lower_than_active() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=90.0)]),
        signal=_signal(),
        evaluation=_evaluation(score=100.0),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(2.0),
        is_duplicate=True,
    )

    assert update is not None
    assert update.update_type == UPDATE_STRENGTHENED
    assert update.public_allowed is False
    assert "score_not_lower_than_active" in update.reasons


def test_detects_strengthened_signal_when_rr_improves() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=None, rr=1.5)]),
        signal=_signal(),
        evaluation=_evaluation(score=70.0),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(2.2),
        is_duplicate=True,
    )

    assert update is not None
    assert update.update_type == UPDATE_STRENGTHENED
    assert "rr_improved_vs_active" in update.reasons


def test_detects_reentry_candidate_for_new_snapshot_with_confirmation() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=None, rr=None, dedupe_key="BTC|long|old")]),
        signal=_signal(dedupe_key="BTC|long|new"),
        evaluation=_evaluation(score=70.0, passed_filters=["candle_confirmation", "secondary_break_of_structure"]),
        entry_snapshot=_snapshot(distance=1.0, bos="bullish_bos"),
        risk_plan=_risk(2.0),
        lifecycle=SignalLifecycleDecision("DUPLICATE", False, "active_same_symbol_direction_without_reentry", 1),
    )

    assert update is not None
    assert update.update_type == UPDATE_REENTRY
    assert update.new_snapshot is True
    assert update.reentry_confirmation is True


def test_detects_invalidation_warning_when_context_worsens() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=90.0, rr=2.0)]),
        signal=_signal(),
        evaluation=_evaluation(
            score=100.0,
            failed_filters=["directional_confluence_failed"],
            rejection_reasons=["quality_score_failed"],
        ),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(2.0),
        setup_context={"market_regime": "RANGING", "avoidance_warnings": ["against_htf"]},
        is_duplicate=True,
    )

    assert update is not None
    assert update.update_type == UPDATE_INVALIDATION
    assert "directional_confluence_failed" in update.risks
    assert "market_regime_ranging" in update.risks


def test_no_update_when_active_signal_has_no_comparable_improvement() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=None, rr=None, dedupe_key="BTC|long|same")]),
        signal=_signal(dedupe_key="BTC|long|same"),
        evaluation=_evaluation(score=100.0),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(2.0),
        is_duplicate=True,
    )

    assert update is not None
    assert update.update_type == UPDATE_NONE
    assert "no_material_update" in update.reasons


def test_returns_none_when_no_active_duplicate_block() -> None:
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([]),
        signal=_signal(),
        evaluation=_evaluation(),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(),
        is_duplicate=False,
    )

    assert update is None


def test_skip_diagnostic_when_duplicate_has_no_active_signal() -> None:
    skip = diagnose_signal_update_v1_skip(
        signal_repo=FakeSignalRepo([]),
        signal=_signal(),
        is_duplicate=True,
        dev_note_enabled=False,
    )

    assert skip is not None
    assert skip.skip_reason == "active_signal_not_found"
    assert skip.public_allowed is False
    assert skip.dev_note_enabled is False
    assert "duplicate_signal_suppressed" in skip.reasons


def test_shadow_report_counts_skipped_events(tmp_path: Path) -> None:
    skip = diagnose_signal_update_v1_skip(
        signal_repo=FakeSignalRepo([]),
        signal=_signal(),
        is_duplicate=True,
    )

    shadow = write_signal_update_v1_shadow_report(reports_path=tmp_path, update=skip)
    text = shadow.read_text(encoding="utf-8")

    assert "active_signal_not_found" in text
    assert '"skipped_events": 1' in text


def test_writes_design_and_shadow_reports(tmp_path: Path) -> None:
    design = write_signal_update_v1_design_report(tmp_path)
    update = evaluate_signal_update_v1(
        signal_repo=FakeSignalRepo([_active(score=90.0)]),
        signal=_signal(),
        evaluation=_evaluation(score=100.0),
        entry_snapshot=_snapshot(),
        risk_plan=_risk(2.0),
        is_duplicate=True,
    )
    shadow = write_signal_update_v1_shadow_report(reports_path=tmp_path, update=update)

    assert design.exists()
    assert shadow.exists()
    assert "SIGNAL_UPDATE_V1" in design.read_text(encoding="utf-8")
    assert "signal_update_v1_skipped" in design.read_text(encoding="utf-8")
    assert "STRENGTHENED_SIGNAL" in shadow.read_text(encoding="utf-8")
