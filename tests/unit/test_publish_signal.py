from __future__ import annotations

from trading_signals.application.use_cases.publish_signal import (
    format_public_signal_message,
    format_telegram_message,
    meta_decision_public_filter_reason,
    publish_filter_rejection_reason,
    publish_signal,
    public_routing_rejection_reason,
)
from trading_signals.app.settings import Settings
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal
from tests.unit.test_strategy_and_risk import build_snapshot


class RecordingSignalRepo:
    def __init__(self) -> None:
        self.deliveries = []

    def save_delivery(self, delivery) -> None:
        self.deliveries.append(delivery)


class RoutingNotifier:
    def __init__(self) -> None:
        self.public_messages = []
        self.dev_messages = []

    def send_public_signal(self, message: str, dry_run: bool = False):
        self.public_messages.append(message)
        return [{"recipient": "public", "status": "sent", "provider_message_id": "public_id"}]

    def send_dev_signal_detail(self, message: str, dry_run: bool = False):
        self.dev_messages.append(message)
        return [{"recipient": "dev", "status": "sent", "provider_message_id": "dev_id"}]


class PublicRiskPlan:
    entry = 100.0
    stop_loss = 105.0
    take_profit = 90.0
    take_profit_2 = 85.0
    take_profit_3 = 80.0


def test_signal_message_contains_clear_direction_for_short() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=1.0,
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
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=[
            "secondary_setup",
            "secondary_trend_alignment",
            "secondary_volume_confirmation",
            "secondary_break_of_structure",
            "secondary_rsi_alignment",
            "quality_score",
        ],
        failed_filters=["distance_to_liquidity_penalty"],
        setup_score=90.0,
        confidence=0.9,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )

    message = format_telegram_message("XRPUSDT", "short", entry, higher, evaluation, risk_plan)

    assert "🚨 Señal XRPUSDT SHORT" in message
    assert "Signal: SHORT" in message
    assert "Direction: SHORT" in message
    assert "📊 Setup" in message
    assert "SIGNAL_TYPE: NEW" in message
    assert "Score: 90.0 ⭐⭐⭐⭐" in message
    assert "📉 Contexto" in message
    assert "💰 Trade" in message
    assert "⚠️ Riesgos" in message
    assert "🧠 Motivo" in message
    assert "tendencia + BOS + volumen + RSI + score válido" in message
    assert "distance_to_liquidity_penalty" not in message


def test_publish_filter_allows_configured_long_london_hour_and_symbol() -> None:
    settings = Settings(
        publish_allowed_directions=["LONG"],
        publish_allowed_sessions=["LONDON"],
        publish_allowed_hours_utc=["11", "15"],
        publish_symbol_whitelist=["AVAXUSDT"],
    )

    reason = publish_filter_rejection_reason(
        settings=settings,
        symbol="AVAXUSDT",
        direction="long",
        setup_context={"session": "LONDON"},
        opened_at="2026-05-07T11:30:00+00:00",
    )

    assert reason is None


def test_publish_filter_rejects_non_matching_fields() -> None:
    base = {
        "settings": Settings(
            publish_allowed_directions=["LONG"],
            publish_allowed_sessions=["LONDON"],
            publish_allowed_hours_utc=["11", "15"],
            publish_symbol_whitelist=["AVAXUSDT"],
        ),
        "symbol": "AVAXUSDT",
        "direction": "long",
        "setup_context": {"session": "LONDON"},
        "opened_at": "2026-05-07T11:30:00+00:00",
    }

    assert publish_filter_rejection_reason(**{**base, "direction": "short"}) == "publish_filter_direction"
    assert publish_filter_rejection_reason(**{**base, "setup_context": {"session": "NEW_YORK"}}) == "publish_filter_session"
    assert publish_filter_rejection_reason(**{**base, "opened_at": "2026-05-07T14:30:00+00:00"}) == "publish_filter_hour_utc"
    assert publish_filter_rejection_reason(**{**base, "symbol": "BTCUSDT"}) == "publish_filter_symbol_whitelist"


def test_publish_filter_empty_config_does_not_restrict() -> None:
    reason = publish_filter_rejection_reason(
        settings=Settings(),
        symbol="BTCUSDT",
        direction="short",
        setup_context={"session": "NEW_YORK"},
        opened_at="2026-05-07T22:30:00+00:00",
    )

    assert reason is None


def test_publish_filter_rejects_blocked_warning_from_context() -> None:
    reason = publish_filter_rejection_reason(
        settings=Settings(publish_blocked_warnings=["dirty_sideways_market"]),
        symbol="BTCUSDT",
        direction="long",
        setup_context={"session": "LONDON", "avoidance_warnings": ["dirty_sideways_market"]},
        opened_at="2026-05-07T11:30:00+00:00",
    )

    assert reason == "publish_filter_blocked_warning:dirty_sideways_market"


def test_publish_filter_rejects_blocked_reason_from_signal_decision() -> None:
    signal_decision = SignalDecision(
        symbol="BTCUSDT",
        direction="long",
        decision="SEND",
        setup_type="MAIN_SIGNAL",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        total_score=82.0,
        rejection_reasons=["directional_confluence_failed"],
        source_engine="test",
    )

    reason = publish_filter_rejection_reason(
        settings=Settings(publish_blocked_reasons=["directional_confluence_failed"]),
        symbol="BTCUSDT",
        direction="long",
        setup_context={"session": "LONDON"},
        opened_at="2026-05-07T11:30:00+00:00",
        evaluation_or_decision=signal_decision,
    )

    assert reason == "publish_filter_blocked_reason:directional_confluence_failed"


def test_publish_filter_rejects_harmful_filter_when_required() -> None:
    signal_decision = SignalDecision(
        symbol="BTCUSDT",
        direction="long",
        decision="SEND",
        setup_type="SECONDARY_SIGNAL",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        total_score=82.0,
        failed_filters=["distance_to_liquidity_penalty"],
        source_engine="test",
    )

    reason = publish_filter_rejection_reason(
        settings=Settings(publish_require_no_harmful_filters=True),
        symbol="BTCUSDT",
        direction="long",
        setup_context={"session": "LONDON"},
        opened_at="2026-05-07T11:30:00+00:00",
        evaluation_or_decision=signal_decision,
    )

    assert reason == "publish_filter_harmful_filter:distance_to_liquidity_penalty"


def test_meta_decision_filter_flag_false_does_not_block() -> None:
    reason = meta_decision_public_filter_reason(
        Settings(meta_decision_filter_enabled=False),
        {"meta_decision": {"meta_decision": "REJECT", "capital_preservation_mode": True}},
    )

    assert reason is None


def test_meta_decision_filter_blocks_reject_trash_and_preservation() -> None:
    settings = Settings(meta_decision_filter_enabled=True)

    assert meta_decision_public_filter_reason(settings, {"meta_decision": {"meta_decision": "REJECT"}}) == "meta_decision_reject"
    assert (
        meta_decision_public_filter_reason(settings, {"meta_decision": {"capital_preservation_mode": True}})
        == "capital_preservation_mode"
    )
    assert (
        meta_decision_public_filter_reason(settings, {"trade_quality": {"trade_quality_grade": "TRASH"}})
        == "trade_quality_trash"
    )


def test_signal_message_accepts_signal_decision_without_changing_payload() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=90.0,
        distance=1.0,
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
    passed_filters = [
        "secondary_setup",
        "secondary_trend_alignment",
        "secondary_volume_confirmation",
        "secondary_break_of_structure",
        "secondary_rsi_alignment",
        "quality_score",
    ]
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
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=passed_filters,
        failed_filters=["distance_to_liquidity_penalty"],
        setup_score=90.0,
        confidence=0.9,
        created_at=entry.created_at,
    )
    signal_decision = SignalDecision(
        symbol="XRPUSDT",
        direction="short",
        decision="SEND",
        setup_type="SECONDARY_SIGNAL",
        entry_price=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        total_score=90.0,
        rejection_reasons=[],
        passed_filters=passed_filters,
        failed_filters=["distance_to_liquidity_penalty"],
        source_engine="liquidity_sweep_mtf_v1",
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )

    evaluation_message = format_telegram_message("XRPUSDT", "short", entry, higher, evaluation, risk_plan)
    decision_message = format_telegram_message("XRPUSDT", "short", entry, higher, signal_decision, risk_plan)

    assert decision_message == evaluation_message


def test_public_signal_message_is_short_and_clean() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="AVAXUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["timeframe_alignment", "primary_sweep_setup", "quality_score"],
        failed_filters=["timeframe_alignment_penalty", "distance_to_liquidity_penalty"],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )

    message = format_public_signal_message("AVAXUSDT", "long", entry, higher, evaluation, risk_plan)

    assert message == (
        "🚨 NUEVA OPERACIÓN 🚨\n\n"
        "🟢 AVAXUSDT\n"
        "📍 Entry: 100.0\n\n"
        "🎯 TP1: 110.0\n\n"
        "🛑 SL: 95.0\n\n"
        "🛡️ Gestiona tu capital con\n"
        "responsabilidad\n\n"
        "🔥 Recomendado:\n"
        "Cerrar parcial en TP1\n"
        "SL break even en TP2"
    )
    assert "TP2:" not in message
    assert "TP3:" not in message
    assert "Timeframes:" not in message
    assert "decision_trace" not in message


def test_public_signal_message_uses_short_emoji_and_optional_tps() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="bearish",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=70.0,
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
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=[],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )

    message = format_public_signal_message("XRPUSDT", "short", entry, higher, evaluation, PublicRiskPlan())

    assert "🔴 XRPUSDT" in message
    assert "🎯 TP1: 90.0" in message
    assert "🎯 TP2: 85.0" in message
    assert "🎯 TP3: 80.0" in message


def test_publish_signal_routes_long_to_public_and_dev() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="AVAXUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["timeframe_alignment", "primary_sweep_setup", "quality_score"],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="AVAXUSDT",
        decision="long",
        status="valid",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()

    deliveries = publish_signal(repo, notifier, signal, entry, higher, evaluation, risk_plan)

    assert len(deliveries) == 2
    assert {delivery.channel for delivery in deliveries} == {"telegram_public", "telegram_dev"}
    assert len(notifier.public_messages) == 1
    assert len(notifier.dev_messages) == 1
    assert "🚨 NUEVA OPERACIÓN 🚨" in notifier.public_messages[0]
    assert "🟢 AVAXUSDT" in notifier.public_messages[0]
    assert "📉 Contexto" not in notifier.public_messages[0]
    assert "📉 Contexto" in notifier.dev_messages[0]


def test_publish_signal_routes_short_ranging_to_dev_only_due_to_negative_edge(caplog) -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="bearish",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=70.0,
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
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["timeframe_alignment", "primary_sweep_setup", "quality_score"],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="XRPUSDT",
        decision="short",
        status="valid",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()

    with caplog.at_level("INFO", logger="trading_signals"):
        deliveries = publish_signal(
            repo,
            notifier,
            signal,
            entry,
            higher,
            evaluation,
            risk_plan,
            setup_context={"market_regime": "RANGING", "setup_type": "MAIN_SIGNAL"},
        )

    assert len(deliveries) == 1
    assert deliveries[0].channel == "telegram_dev"
    assert notifier.public_messages == []
    assert len(notifier.dev_messages) == 1
    assert "🚨 Señal XRPUSDT SHORT" in notifier.dev_messages[0]
    assert "signal routed to DEV/paper only due to negative historical edge" in caplog.text


def test_publish_signal_with_public_block_reason_still_sends_dev_only(caplog) -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["timeframe_alignment", "primary_sweep_setup", "quality_score"],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision="long",
        status="valid",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()

    with caplog.at_level("INFO", logger="trading_signals"):
        deliveries = publish_signal(
            repo,
            notifier,
            signal,
            entry,
            higher,
            evaluation,
            risk_plan,
            public_block_reason="meta_decision_reject",
        )

    assert {delivery.channel for delivery in deliveries} == {"telegram_dev"}
    assert notifier.public_messages == []
    assert len(notifier.dev_messages) == 1
    assert "signal routed to DEV/paper only due to public filter" in caplog.text


def test_publish_signal_routes_secondary_short_to_dev_only(caplog) -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="OPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="OPUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="OPUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="short",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["secondary_setup", "secondary_trend_alignment", "quality_score"],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=105.0,
        take_profit=90.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="OPUSDT",
        decision="short",
        status="valid",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()

    with caplog.at_level("INFO", logger="trading_signals"):
        deliveries = publish_signal(
            repo,
            notifier,
            signal,
            entry,
            higher,
            evaluation,
            risk_plan,
            setup_context={"market_regime": "TRENDING", "setup_type": "SECONDARY_SIGNAL"},
        )

    assert {delivery.channel for delivery in deliveries} == {"telegram_dev"}
    assert notifier.public_messages == []
    assert len(notifier.dev_messages) == 1
    assert "signal routed to DEV/paper only due to negative historical edge" in caplog.text


def test_publish_signal_routes_secondary_choppy_range_to_dev_only() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="none",
        score=88.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="ADAUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["secondary_setup", "secondary_trend_alignment", "quality_score"],
        failed_filters=[],
        setup_score=88.0,
        confidence=0.88,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="ADAUSDT",
        decision="long",
        status="valid",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()

    deliveries = publish_signal(
        repo,
        notifier,
        signal,
        entry,
        higher,
        evaluation,
        risk_plan,
        setup_context={"market_regime": "RANGING", "setup_type": "SECONDARY_SIGNAL", "entry_context": "CHOPPY_RANGE"},
    )

    assert {delivery.channel for delivery in deliveries} == {"telegram_dev"}
    assert notifier.public_messages == []
    assert len(notifier.dev_messages) == 1


def test_public_routing_allows_long_breakout_main_signal() -> None:
    signal = type("Signal", (), {"decision": "long"})()
    evaluation = type("Evaluation", (), {"setup_type": "MAIN_SIGNAL", "passed_filters": []})()

    reason = public_routing_rejection_reason(
        signal,
        evaluation,
        {
            "market_regime": "TRENDING",
            "setup_type": "MAIN_SIGNAL",
            "entry_context": "BREAKOUT",
            "trade_location": "mid_range",
            "trend_higher": "bullish",
        },
    )

    assert reason is None


def test_public_routing_blocks_against_htf_warning() -> None:
    signal = type("Signal", (), {"decision": "long"})()
    evaluation = type("Evaluation", (), {"setup_type": "MAIN_SIGNAL", "passed_filters": []})()

    reason = public_routing_rejection_reason(
        signal,
        evaluation,
        {"market_regime": "TRENDING", "setup_type": "MAIN_SIGNAL", "avoidance_warnings": ["against_htf"]},
    )

    assert reason == "public_block_against_htf"


def test_public_routing_blocks_breakout_with_range_and_timeframe_penalties() -> None:
    signal = type("Signal", (), {"decision": "long"})()
    evaluation = type("Evaluation", (), {"setup_type": "MAIN_SIGNAL", "passed_filters": [], "decision_trace": []})()

    reason = public_routing_rejection_reason(
        signal,
        evaluation,
        {
            "market_regime": "TRENDING",
            "setup_type": "MAIN_SIGNAL",
            "entry_context": "BREAKOUT",
            "trade_location": "mid_range",
            "penalties": ["market_structure_range_penalty:10", "timeframe_alignment_penalty:10"],
        },
    )

    assert reason == "public_block_bad_breakout_context"


def test_public_routing_blocks_breakout_in_bad_contexts() -> None:
    signal = type("Signal", (), {"decision": "short"})()
    evaluation = type("Evaluation", (), {"setup_type": "MAIN_SIGNAL", "passed_filters": []})()

    assert public_routing_rejection_reason(
        signal,
        evaluation,
        {"market_regime": "RANGING", "entry_context": "BREAKOUT", "trade_location": "mid_range"},
    ) == "public_block_breakout_ranging"
    assert public_routing_rejection_reason(
        signal,
        evaluation,
        {"market_regime": "TRENDING", "entry_context": "BREAKOUT", "trade_location": "near_support"},
    ) == "public_block_breakout_bad_location"
    assert public_routing_rejection_reason(
        signal,
        evaluation,
        {"market_regime": "TRENDING", "entry_context": "BREAKOUT", "trade_location": "mid_range", "trend_higher": "bullish"},
    ) == "public_block_breakout_against_htf"
