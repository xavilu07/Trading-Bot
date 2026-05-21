from trading_signals.app.settings import Settings
from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.application.use_cases.analyze_symbol import analyze_symbol
from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.services.risk_service import calculate_risk_plan
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1
from tests.fixtures.market_data import FakeMarketDataClient, generate_trend_dataset


def build_settings(tmp_path) -> Settings:
    return Settings(data_storage_path=tmp_path)


def test_strategy_returns_long_for_bullish_fixture(tmp_path) -> None:
    settings = build_settings(tmp_path)
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    analysis = analyze_symbol(market_data=market_data, settings=settings, scan_run_id="run_test", symbol="BTCUSDT")
    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", analysis.entry_snapshot.created_at)
    assert evaluation.decision == "long"
    assert "timeframe_alignment" in evaluation.passed_filters


def test_risk_plan_is_valid_for_long(tmp_path) -> None:
    settings = build_settings(tmp_path)
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    analysis = analyze_symbol(market_data=market_data, settings=settings, scan_run_id="run_test", symbol="BTCUSDT")
    risk_plan = calculate_risk_plan(
        risk_plan_id="risk_test",
        evaluation_id="eval_test",
        decision="long",
        snapshot=analysis.entry_snapshot,
        min_rr=settings.min_rr,
        risk_per_trade=settings.risk_per_trade,
        account_balance_reference=settings.account_balance_reference,
        created_at=analysis.entry_snapshot.created_at,
    )
    assert risk_plan is not None
    assert risk_plan.stop_loss < risk_plan.entry < risk_plan.take_profit
    assert risk_plan.risk_reward >= settings.min_rr


def build_snapshot(
    *,
    scan_run_id: str,
    symbol: str,
    timeframe: str,
    trend: str,
    structure: str,
    sweep: str,
    score: float,
    distance: float,
    nearest_distance: float | None = None,
    rsi: float = 40.0,
    volume_ratio: float = 2.0,
    break_of_structure: str = "none",
    timestamp: str = "2026-01-01T08:00:00+00:00",
) -> MarketSnapshot:
    return MarketSnapshot(
        id=f"snap_{symbol}_{timeframe}",
        scan_run_id=scan_run_id,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=100.0,
        high=102.0,
        low=98.0,
        close=101.0,
        volume=2000.0,
        trend=trend,
        market_structure=structure,
        liquidity_high=110.0,
        liquidity_low=95.0,
        liquidity_sweep=sweep,
        atr=1.0,
        body_ratio=0.7,
        distance_to_liquidity_atr=distance,
        setup_score=score,
        created_at=timestamp,
        metadata={
            "rsi": rsi,
            "break_of_structure": break_of_structure,
            "volume_ratio_vs_average_20": volume_ratio,
            "nearest_distance_to_liquidity_atr": nearest_distance if nearest_distance is not None else distance,
        },
    )


def test_range_can_produce_long_when_sweep_volume_and_rsi_are_favorable(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="DOGEUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="bullish_sweep",
        score=80.0,
        distance=3.0,
        rsi=35.0,
        volume_ratio=2.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="DOGEUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("DOGEUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert "market_structure_range_penalty" in evaluation.failed_filters
    assert "distance_to_liquidity_penalty" in evaluation.failed_filters
    assert evaluation.setup_score == 60.0


def test_higher_timeframe_clear_contradiction_blocks_direction(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish_sweep",
        score=90.0,
        distance=1.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("BTCUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "timeframe_alignment_penalty" in evaluation.failed_filters
    assert "higher_timeframe_contradicts_long" in evaluation.failed_filters


def test_secondary_setup_can_generate_long_without_sweep(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("XRPUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert "secondary_setup" in evaluation.passed_filters
    assert "primary_sweep_setup" not in evaluation.passed_filters
    assert "setup_type=SECONDARY_SIGNAL" in evaluation.decision_trace


def test_secondary_setup_requires_higher_score_than_primary_threshold(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=20.0,
        distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("XRPUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "secondary_setup_requirements_failed" in evaluation.failed_filters


def test_main_signal_keeps_directional_distance_extreme_as_hard_block(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish_sweep",
        score=90.0,
        distance=6.0,
        nearest_distance=1.0,
        rsi=42.0,
        volume_ratio=2.0,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("BTCUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "distance_to_liquidity_extreme" in evaluation.failed_filters
    assert "primary_sweep_setup" not in evaluation.passed_filters
    assert "directional_distance_check=extreme" in evaluation.decision_trace


def test_secondary_setup_uses_nearest_liquidity_when_directional_distance_is_extreme(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=65.0,
        distance=6.0,
        nearest_distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("SOLUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert evaluation.setup_score == 80.0
    assert "secondary_setup" in evaluation.passed_filters
    assert "secondary_nearest_liquidity" in evaluation.passed_filters
    assert "distance_to_liquidity_extreme" in evaluation.failed_filters
    assert "nearest_liquidity_extreme" not in evaluation.failed_filters
    assert "directional_distance_check=extreme" in evaluation.decision_trace
    assert "nearest_liquidity_check=passed" in evaluation.decision_trace
    assert "liquidity_rule_applied=nearest_secondary_continuation" in evaluation.decision_trace
    assert "secondary_confluence_bonus=35" in evaluation.decision_trace


def test_secondary_setup_blocks_when_nearest_liquidity_is_extreme(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=90.0,
        distance=6.0,
        nearest_distance=3.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("SOLUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "nearest_liquidity_extreme" in evaluation.failed_filters
    assert "secondary_nearest_liquidity" not in evaluation.passed_filters
    assert "nearest_liquidity_check=extreme" in evaluation.decision_trace


def test_secondary_setup_allows_range_only_when_bos_confirms_structure(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="none",
        score=90.0,
        distance=1.0,
        nearest_distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("SOLUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert "market_structure_range_penalty" in evaluation.failed_filters
    assert "secondary_setup" in evaluation.passed_filters


def test_secondary_setup_blocks_range_without_bos(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="none",
        score=90.0,
        distance=1.0,
        nearest_distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="none",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="SOLUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("SOLUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "market_structure_range_penalty" in evaluation.failed_filters
    assert "secondary_setup" not in evaluation.passed_filters


def test_range_setup_allowed_by_score_and_two_quality_checks(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="1h",
        trend="bearish",
        structure="range",
        sweep="bearish_sweep",
        score=85.0,
        distance=1.0,
        rsi=50.0,
        volume_ratio=1.3,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("ADAUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "short"
    assert "market_structure_range_penalty" in evaluation.failed_filters
    assert "market_structure_range_allowed" in evaluation.passed_filters
    assert "range_quality_allowed=True" in evaluation.decision_trace


def test_range_setup_with_low_score_stays_blocked(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="1h",
        trend="bearish",
        structure="range",
        sweep="bearish_sweep",
        score=70.0,
        distance=1.0,
        rsi=50.0,
        volume_ratio=1.3,
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="ADAUSDT",
        timeframe="4h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("ADAUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "market_structure_range_penalty" in evaluation.failed_filters
    assert "market_structure_range_allowed" not in evaluation.passed_filters


def test_directional_confluence_soft_allows_high_score_without_strong_htf_contradiction(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=100.0,
        distance=1.0,
        rsi=58.0,
        volume_ratio=1.0,
        break_of_structure="bullish_bos",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="AVAXUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
    )
    analysis = AnalysisResult("AVAXUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert "secondary_setup_requirements_failed" in evaluation.failed_filters
    assert "secondary_setup_requirements_failed:20" in ",".join(evaluation.decision_trace)
    assert "directional_confluence_soft_allowed" in evaluation.passed_filters
    assert "directional_confluence_failed" not in evaluation.failed_filters


def test_asia_blocks_secondary_signal_even_when_other_requirements_pass(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=100.0,
        distance=1.0,
        rsi=58.0,
        volume_ratio=1.8,
        break_of_structure="bullish_bos",
        timestamp="2026-01-01T02:00:00+00:00",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
        timestamp="2026-01-01T02:00:00+00:00",
    )
    analysis = AnalysisResult("XRPUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "asia_secondary_setup_blocked" in evaluation.failed_filters
    assert "secondary_setup" not in evaluation.passed_filters
    assert "session=ASIA" in evaluation.decision_trace


def test_asia_requires_main_signal_score_85(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish_sweep",
        score=84.0,
        distance=1.0,
        timestamp="2026-01-01T02:00:00+00:00",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
        timestamp="2026-01-01T02:00:00+00:00",
    )
    analysis = AnalysisResult("BTCUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "no_trade"
    assert "primary_sweep_setup" not in evaluation.passed_filters
    assert "asia_session_threshold_adjustment=10" in evaluation.decision_trace


def test_asia_allows_main_signal_score_85_or_more(tmp_path) -> None:
    settings = build_settings(tmp_path)
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish_sweep",
        score=90.0,
        distance=1.0,
        timestamp="2026-01-01T02:00:00+00:00",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=60.0,
        distance=1.0,
        timestamp="2026-01-01T02:00:00+00:00",
    )
    analysis = AnalysisResult("BTCUSDT", "1h", "4h", entry, higher)

    evaluation = LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", entry.created_at)

    assert evaluation.decision == "long"
    assert "primary_sweep_setup" in evaluation.passed_filters
    assert "session=ASIA" in evaluation.decision_trace
