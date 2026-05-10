from __future__ import annotations

from trading_signals.application.use_cases.signal_lifecycle import classify_signal_lifecycle
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from tests.unit.test_strategy_and_risk import build_snapshot


class FakeSignalRepo:
    def __init__(self, signals: list[dict[str, object]]) -> None:
        self.signals = signals

    def list_latest_signals(self, limit: int = 20) -> list[dict[str, object]]:
        return self.signals[:limit]


def build_evaluation(*, passed_filters: list[str], failed_filters: list[str]) -> StrategyEvaluation:
    return StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="XRPUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=passed_filters,
        failed_filters=failed_filters,
        setup_score=90.0,
        confidence=0.9,
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_first_signal_is_new() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=1.0,
    )

    decision = classify_signal_lifecycle(
        signal_repo=FakeSignalRepo([]),
        symbol="XRPUSDT",
        direction="short",
        entry_snapshot=snapshot,
        evaluation=build_evaluation(passed_filters=["candle_confirmation"], failed_filters=[]),
    )

    assert decision.signal_type == "NEW"
    assert decision.should_publish is True


def test_existing_signal_without_pullback_is_duplicate() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=4.0,
        nearest_distance=3.0,
    )
    repo = FakeSignalRepo([
        {"symbol": "XRPUSDT", "decision": "short", "published_at": "2026-01-01T00:00:00+00:00"}
    ])

    decision = classify_signal_lifecycle(
        signal_repo=repo,
        symbol="XRPUSDT",
        direction="short",
        entry_snapshot=snapshot,
        evaluation=build_evaluation(passed_filters=["candle_confirmation"], failed_filters=[]),
    )

    assert decision.signal_type == "DUPLICATE"
    assert decision.should_publish is False
    assert decision.reason == "active_same_symbol_direction_without_reentry"


def test_existing_signal_with_pullback_and_bos_is_reentry() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=1.0,
        break_of_structure="bearish_bos",
    )
    repo = FakeSignalRepo([
        {"symbol": "XRPUSDT", "decision": "short", "published_at": "2026-01-01T00:00:00+00:00"}
    ])

    decision = classify_signal_lifecycle(
        signal_repo=repo,
        symbol="XRPUSDT",
        direction="short",
        entry_snapshot=snapshot,
        evaluation=build_evaluation(
            passed_filters=["candle_confirmation", "secondary_break_of_structure"],
            failed_filters=[],
        ),
    )

    assert decision.signal_type == "REENTRY"
    assert decision.should_publish is True
    assert decision.reason == "pullback_and_confirmation"


def test_max_reentries_blocks_signal() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=1.0,
        break_of_structure="bearish_bos",
    )
    repo = FakeSignalRepo([
        {"symbol": "XRPUSDT", "decision": "short", "published_at": "2026-01-01T00:00:00+00:00"},
        {"symbol": "XRPUSDT", "decision": "short", "published_at": "2026-01-01T01:00:00+00:00"},
        {"symbol": "XRPUSDT", "decision": "short", "published_at": "2026-01-01T02:00:00+00:00"},
    ])

    decision = classify_signal_lifecycle(
        signal_repo=repo,
        symbol="XRPUSDT",
        direction="short",
        entry_snapshot=snapshot,
        evaluation=build_evaluation(
            passed_filters=["candle_confirmation", "secondary_break_of_structure"],
            failed_filters=[],
        ),
    )

    assert decision.signal_type == "DUPLICATE"
    assert decision.should_publish is False
    assert decision.reason == "max_reentries_reached"
