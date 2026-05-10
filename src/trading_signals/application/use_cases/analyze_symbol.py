from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from trading_signals.app.settings import Settings
from trading_signals.analysis.liquidity import detect_liquidity_sweep, get_liquidity_levels, liquidity_context
from trading_signals.analysis.momentum import compute_rsi, volume_profile
from trading_signals.analysis.trend import detect_break_of_structure, detect_trend
from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.services.candle_confirmation_service import body_ratio
from trading_signals.domain.services.scoring_service import compute_setup_score
from trading_signals.domain.services.structure_service import detect_structure
from trading_signals.domain.services.volatility_service import compute_atr


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


_compute_rsi = compute_rsi
_detect_break_of_structure = detect_break_of_structure


def _build_snapshot(
    *,
    scan_run_id: str,
    symbol: str,
    timeframe: str,
    candles: list[dict[str, float | str]],
) -> MarketSnapshot:
    closes = [float(item["close"]) for item in candles]
    highs = [float(item["high"]) for item in candles]
    lows = [float(item["low"]) for item in candles]
    volumes = [float(item["volume"]) for item in candles]
    last = candles[-1]
    trend, trend_meta = detect_trend(closes)
    structure = detect_structure(highs, lows)
    liquidity_high, liquidity_low = get_liquidity_levels(highs, lows)
    sweep = detect_liquidity_sweep(candles)
    atr = compute_atr(candles)
    close_price = float(last["close"])
    liquidity = liquidity_context(
        close_price=close_price,
        trend=trend,
        liquidity_high=liquidity_high,
        liquidity_low=liquidity_low,
        atr=atr,
    )
    distance_to_liquidity_atr = float(liquidity["distance_to_liquidity_atr"])
    body_ratio_value = body_ratio(last)
    atr_ratio = atr / close_price if close_price else 0.0
    score = compute_setup_score(trend, structure, sweep, body_ratio_value, distance_to_liquidity_atr, atr_ratio)
    rsi = compute_rsi(closes)
    break_of_structure = detect_break_of_structure(candles)
    volume = volume_profile(volumes)
    recent = candles[-9:-1]
    recent_close_high = max(float(item["close"]) for item in recent) if recent else close_price
    recent_close_low = min(float(item["close"]) for item in recent) if recent else close_price
    created_at = _now_iso()
    metadata = {
        **trend_meta,
        "rsi": round(rsi, 6),
        "break_of_structure": break_of_structure,
        "directional_liquidity_level": round(float(liquidity["directional_liquidity_level"]), 6),
        "directional_liquidity_side": liquidity["directional_liquidity_side"],
        "nearest_liquidity_level": round(float(liquidity["nearest_liquidity_level"]), 6),
        "nearest_liquidity_side": liquidity["nearest_liquidity_side"],
        "nearest_distance_to_liquidity_atr": round(float(liquidity["nearest_distance_to_liquidity_atr"]), 6),
        "volume_average_20": round(volume["average"], 6),
        "volume_ratio_vs_average_20": round(volume["ratio"], 6),
        "recent_close_high_before_bos": round(recent_close_high, 6),
        "recent_close_low_before_bos": round(recent_close_low, 6),
    }
    return MarketSnapshot(
        id=f"snap_{uuid4().hex[:12]}",
        scan_run_id=scan_run_id,
        symbol=symbol,
        timeframe=timeframe,
        timestamp=str(last["close_time"]),
        open=float(last["open"]),
        high=float(last["high"]),
        low=float(last["low"]),
        close=close_price,
        volume=volumes[-1],
        trend=trend,
        market_structure=structure,
        liquidity_high=round(liquidity_high, 6),
        liquidity_low=round(liquidity_low, 6),
        liquidity_sweep=sweep,
        atr=round(atr, 6),
        body_ratio=round(body_ratio_value, 6),
        distance_to_liquidity_atr=round(distance_to_liquidity_atr, 6),
        setup_score=score,
        created_at=created_at,
        metadata=metadata,
    )


def analyze_symbol(
    *,
    market_data,
    settings: Settings,
    scan_run_id: str,
    symbol: str,
) -> AnalysisResult:
    symbol = market_data.normalize_symbol(symbol) if hasattr(market_data, "normalize_symbol") else symbol.strip().upper()
    fetch = market_data.get_ohlcv if hasattr(market_data, "get_ohlcv") else market_data.fetch_ohlcv
    entry = fetch(symbol, settings.entry_timeframe)
    higher = fetch(symbol, settings.higher_timeframe)
    if len(entry) < 220 or len(higher) < 220:
        raise ValueError(f"Insufficient candle history for {symbol}")
    entry_snapshot = _build_snapshot(scan_run_id=scan_run_id, symbol=symbol, timeframe=settings.entry_timeframe, candles=entry)
    higher_snapshot = _build_snapshot(scan_run_id=scan_run_id, symbol=symbol, timeframe=settings.higher_timeframe, candles=higher)
    source = getattr(market_data, "provider_name", entry_snapshot.source)
    entry_snapshot.source = source
    higher_snapshot.source = source
    return AnalysisResult(
        symbol=symbol,
        entry_timeframe=settings.entry_timeframe,
        higher_timeframe=settings.higher_timeframe,
        entry_snapshot=entry_snapshot,
        higher_snapshot=higher_snapshot,
    )
