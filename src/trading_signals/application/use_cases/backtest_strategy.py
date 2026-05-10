from __future__ import annotations

from trading_signals.application.use_cases.analyze_symbol import _build_snapshot
from trading_signals.app.settings import Settings
from trading_signals.domain.services.risk_service import calculate_risk_plan
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1


def backtest_strategy(dataset: list[dict[str, float | str]], symbol: str, settings: Settings) -> dict[str, float | int]:
    if len(dataset) < 240:
        raise ValueError("Dataset too small for backtest")
    strategy = LiquiditySweepMTFV1(settings)
    wins = 0
    losses = 0
    total_r = 0.0
    trades = 0
    for end_idx in range(220, len(dataset) - 8):
        entry_window = dataset[: end_idx + 1]
        higher_window = dataset[: end_idx + 1]
        future_window = dataset[end_idx + 1:end_idx + 9]
        entry_snapshot = _build_snapshot(scan_run_id="bt", symbol=symbol, timeframe=settings.entry_timeframe, candles=entry_window)
        higher_snapshot = _build_snapshot(scan_run_id="bt", symbol=symbol, timeframe=settings.higher_timeframe, candles=higher_window)
        analysis = type("AnalysisResultProxy", (), {"entry_snapshot": entry_snapshot, "higher_snapshot": higher_snapshot, "symbol": symbol, "entry_timeframe": settings.entry_timeframe, "higher_timeframe": settings.higher_timeframe})()
        evaluation = strategy.evaluate(analysis, evaluation_id=f"eval_bt_{end_idx}", created_at=entry_snapshot.created_at)
        if evaluation.decision == "no_trade":
            continue
        risk_plan = calculate_risk_plan(
            risk_plan_id=f"risk_bt_{end_idx}",
            evaluation_id=evaluation.id,
            decision=evaluation.decision,
            snapshot=entry_snapshot,
            min_rr=settings.min_rr,
            risk_per_trade=settings.risk_per_trade,
            account_balance_reference=settings.account_balance_reference,
            created_at=entry_snapshot.created_at,
        )
        if not risk_plan:
            continue
        trades += 1
        outcome = None
        for candle in future_window:
            high = float(candle["high"])
            low = float(candle["low"])
            if evaluation.decision == "long":
                if low <= risk_plan.stop_loss:
                    losses += 1
                    total_r -= 1.0
                    outcome = "loss"
                    break
                if high >= risk_plan.take_profit:
                    wins += 1
                    total_r += risk_plan.risk_reward
                    outcome = "win"
                    break
            else:
                if high >= risk_plan.stop_loss:
                    losses += 1
                    total_r -= 1.0
                    outcome = "loss"
                    break
                if low <= risk_plan.take_profit:
                    wins += 1
                    total_r += risk_plan.risk_reward
                    outcome = "win"
                    break
        if outcome is None:
            pass
    closed = wins + losses
    win_rate = round((wins / closed) * 100, 2) if closed else 0.0
    return {"total_trades": trades, "wins": wins, "losses": losses, "win_rate_closed": win_rate, "total_r": round(total_r, 2)}

