from __future__ import annotations

from datetime import UTC, datetime

from trading_signals.application.use_cases.active_signal_cleanup_shadow_v1 import (
    CLEANUP_LIKELY_ZOMBIE,
    CLEANUP_RECENT,
    CLEANUP_STALE,
    CLEANUP_UNKNOWN,
    classify_active_signal_for_cleanup,
    evaluate_active_signal_cleanup_shadow_v1,
)
from trading_signals.application.use_cases.signal_lifecycle import SignalLifecycleDecision
from trading_signals.domain.entities.trade_signal import TradeSignal


class FakeSignalRepo:
    def __init__(self, signals: list[dict[str, object]]) -> None:
        self.signals = signals

    def list_latest_signals(self, limit: int = 20) -> list[dict[str, object]]:
        return self.signals[:limit]


def _now() -> datetime:
    return datetime(2026, 1, 4, 12, 0, tzinfo=UTC)


def _signal() -> TradeSignal:
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
        dedupe_key="BTC|long|new",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        created_at="2026-01-04T12:00:00+00:00",
    )


def test_classifies_likely_zombie_without_expiration_or_close_reason() -> None:
    assessment = classify_active_signal_for_cleanup(
        {
            "id": "sig_active",
            "symbol": "BTCUSDT",
            "decision": "long",
            "published_at": "2026-01-01T00:00:00+00:00",
        },
        now=_now(),
    )

    assert assessment.classification == CLEANUP_LIKELY_ZOMBIE
    assert assessment.age_hours == 84.0
    assert "missing_expires_at" in assessment.reasons
    assert "missing_close_reason" in assessment.reasons


def test_classifies_stale_after_24h() -> None:
    assessment = classify_active_signal_for_cleanup(
        {
            "id": "sig_active",
            "symbol": "ETHUSDT",
            "decision": "short",
            "published_at": "2026-01-03T00:00:00+00:00",
            "expires_at": "2026-01-05T00:00:00+00:00",
        },
        now=_now(),
    )

    assert assessment.classification == CLEANUP_STALE
    assert "age_gt_24h" in assessment.reasons


def test_classifies_recent_within_24h() -> None:
    assessment = classify_active_signal_for_cleanup(
        {
            "id": "sig_active",
            "symbol": "ETHUSDT",
            "decision": "long",
            "published_at": "2026-01-04T00:00:00+00:00",
        },
        now=_now(),
    )

    assert assessment.classification == CLEANUP_RECENT


def test_classifies_unknown_without_timestamp() -> None:
    assessment = classify_active_signal_for_cleanup(
        {"id": "sig_active", "symbol": "ETHUSDT", "decision": "long"},
        now=_now(),
    )

    assert assessment.classification == CLEANUP_UNKNOWN
    assert "missing_published_at_or_created_at" in assessment.reasons


def test_evaluates_duplicate_blocked_by_likely_zombie_shadow_only() -> None:
    result = evaluate_active_signal_cleanup_shadow_v1(
        signal_repo=FakeSignalRepo(
            [
                {
                    "id": "sig_active",
                    "symbol": "BTCUSDT",
                    "decision": "long",
                    "published_at": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
        signal=_signal(),
        is_duplicate=True,
        now=_now(),
    )

    assert result is not None
    assert result["shadow_only"] is True
    assert result["public_allowed"] is False
    assert result["cleanup_classification"] == CLEANUP_LIKELY_ZOMBIE
    assert result["estimated_released_candidate_if_cleanup"] is True
    assert result["likely_zombie_count"] == 1


def test_evaluates_lifecycle_block_even_if_exact_duplicate_false() -> None:
    result = evaluate_active_signal_cleanup_shadow_v1(
        signal_repo=FakeSignalRepo(
            [
                {
                    "id": "sig_active",
                    "symbol": "BTCUSDT",
                    "decision": "long",
                    "published_at": "2026-01-01T00:00:00+00:00",
                }
            ]
        ),
        signal=_signal(),
        is_duplicate=False,
        lifecycle=SignalLifecycleDecision("DUPLICATE", False, "active_same_symbol_direction_without_reentry", 1),
        now=_now(),
    )

    assert result is not None
    assert result["cleanup_classification"] == CLEANUP_LIKELY_ZOMBIE
    assert result["lifecycle_reason"] == "active_same_symbol_direction_without_reentry"


def test_returns_none_when_no_duplicate_or_lifecycle_block() -> None:
    result = evaluate_active_signal_cleanup_shadow_v1(
        signal_repo=FakeSignalRepo([]),
        signal=_signal(),
        is_duplicate=False,
        now=_now(),
    )

    assert result is None
