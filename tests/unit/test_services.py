from trading_signals.domain.services.candle_confirmation_service import body_ratio
from trading_signals.domain.services.liquidity_service import detect_liquidity_sweep, get_liquidity_levels
from trading_signals.domain.services.scoring_service import compute_setup_score
from trading_signals.domain.services.structure_service import detect_structure
from trading_signals.domain.services.trend_service import detect_trend
from trading_signals.domain.services.volatility_service import compute_atr
from tests.fixtures.market_data import generate_trend_dataset


def test_trend_service_detects_bullish_trend() -> None:
    dataset = generate_trend_dataset(direction="up")
    closes = [float(item["close"]) for item in dataset]
    trend, meta = detect_trend(closes)
    assert trend == "bullish"
    assert meta["ema20"] > meta["ema50"]


def test_structure_service_detects_bullish_structure() -> None:
    dataset = generate_trend_dataset(direction="up")
    highs = [float(item["high"]) for item in dataset]
    lows = [float(item["low"]) for item in dataset]
    assert detect_structure(highs, lows) == "bullish"


def test_liquidity_and_sweep_detected() -> None:
    dataset = generate_trend_dataset(direction="up")
    highs = [float(item["high"]) for item in dataset]
    lows = [float(item["low"]) for item in dataset]
    liquidity_high, liquidity_low = get_liquidity_levels(highs, lows)
    assert liquidity_high > liquidity_low
    assert detect_liquidity_sweep(dataset) == "bullish_sweep"


def test_atr_body_ratio_and_score() -> None:
    dataset = generate_trend_dataset(direction="up")
    atr = compute_atr(dataset)
    ratio = body_ratio(dataset[-1])
    score = compute_setup_score("bullish", "bullish", "bullish_sweep", ratio, 0.8, atr / float(dataset[-1]["close"]))
    assert atr > 0
    assert 0 <= ratio <= 1
    assert score >= 60

