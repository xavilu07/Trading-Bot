from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.application.policies.public_canary_policy import PublicShortCanaryConfig
from trading_signals.application.policies.public_safety_policy import evaluate_public_safety_policy
from trading_signals.application.policies.relaxed_public_safety_v2 import evaluate_relaxed_public_safety_v2
from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


SUMMARY_FIELDS = [
    "layer",
    "mode",
    "trades_evaluated",
    "trades_accepted",
    "trades_rejected",
    "total_r",
    "winrate",
    "avg_r",
    "profit_factor",
    "max_drawdown",
    "current_drawdown",
    "delta_total_r_vs_baseline",
    "delta_winrate_vs_baseline",
    "delta_total_r_vs_current_policy",
    "delta_accepted_vs_current_policy",
    "sample_size",
    "confidence",
    "top_rejection_reasons",
    "top_allowed_contexts",
    "top_blocked_contexts",
]


@dataclass(frozen=True)
class BacktestConfig:
    mode: str = "shadow"
    min_trades: int = 1
    max_daily_loss_r: float = 2.0
    max_consecutive_losses: int = 2
    max_weekly_drawdown_r: float = 4.0
    kill_switch_cooldown_hours: float = 12.0
    protection_symbol_loss_cooldown_hours: float = 6.0
    protection_max_drawdown_guard_r: float = 4.0
    protection_max_drawdown_lookback_days: float = 7.0
    protection_low_profit_min_trades: int = 5
    protection_low_profit_min_avg_r: float = -0.2
    protection_low_profit_lookback_days: float = 14.0
    pair_universe_performance_min_trades: int = 3
    pair_universe_min_recent_avg_r: float = -0.5
    pair_universe_performance_lookback_days: float = 14.0
    canary_min_score: float = 70.0


def run_backtest_runner(
    *,
    data_path: Path,
    reports_path: Path,
    config: BacktestConfig | None = None,
) -> dict[str, object]:
    cfg = config or BacktestConfig()
    trades = load_real_trades(data_path)
    signals: list[dict[str, Any]] = []
    layers = _evaluate_layers(trades, signals, cfg=cfg)
    baseline = layers[0]["metrics"] if layers else _metrics([])
    current_policy = next((layer["metrics"] for layer in layers if layer["layer"] == "public_safety_policy"), baseline)
    for layer in layers:
        metrics = layer["metrics"]
        metrics["delta_total_r_vs_baseline"] = round(float(metrics["total_r"]) - float(baseline["total_r"]), 4)
        metrics["delta_winrate_vs_baseline"] = round(float(metrics["winrate"]) - float(baseline["winrate"]), 4)
        metrics["delta_total_r_vs_current_policy"] = round(float(metrics["total_r"]) - float(current_policy["total_r"]), 4)
        metrics["delta_accepted_vs_current_policy"] = int(metrics["trades_accepted"]) - int(current_policy["trades_accepted"])
        layer["top_improved_contexts"] = _context_delta_rows(layer["rejected_trades"], improvement=True)
        layer["top_worsened_contexts"] = _context_delta_rows(layer["rejected_trades"], improvement=False)
        layer["top_allowed_contexts"] = _context_rank_rows(layer["accepted_trades"], best=True)
        layer["top_blocked_contexts"] = _context_rank_rows(layer["rejected_trades"], best=False)

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": cfg.mode,
        "data_path": str(data_path),
        "trades_loaded": len(trades),
        "baseline_layer": "raw_strategy",
        "layers": [_public_layer(layer) for layer in layers],
    }
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "backtest_runner_report.json"
    csv_path = reports_path / "backtest_runner_report.csv"
    md_path = reports_path / "backtest_runner_summary.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_summary_csv(csv_path, layers, cfg=cfg)
    md_path.write_text(format_backtest_runner_summary(report), encoding="utf-8")
    return {
        "report": report,
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "summary_path": str(md_path),
    }


def load_real_trades(data_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in load_canonical_closed_trades(data_path):
        timestamp = _parse_datetime(str(row.get("timestamp") or ""))
        if timestamp is None:
            continue
        rows.append({**row, "timestamp": timestamp, "source": "canonical:paper_trading/trades.csv"})
    return rows


def format_backtest_runner_summary(report: dict[str, object]) -> str:
    layers = [item for item in report.get("layers", []) if isinstance(item, dict)]
    lines = [
        "# Backtest Runner Summary",
        "",
        f"- Generated at: {report.get('generated_at')}",
        f"- Mode: {report.get('mode')}",
        f"- Trades loaded: {report.get('trades_loaded', 0)}",
        "",
        "| Layer | Evaluated | Accepted | Rejected | Total R | WR | Avg R | PF | Max DD | Delta R | Delta vs Current | Confidence |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for layer in layers:
        metrics = _dict(layer.get("metrics"))
        lines.append(
            "| {layer} | {evaluated} | {accepted} | {rejected} | {total_r} | {wr}% | {avg_r} | {pf} | {dd} | {delta} | {delta_current} | {confidence} |".format(
                layer=layer.get("layer"),
                evaluated=metrics.get("trades_evaluated", 0),
                accepted=metrics.get("trades_accepted", 0),
                rejected=metrics.get("trades_rejected", 0),
                total_r=metrics.get("total_r", 0),
                wr=metrics.get("winrate", 0),
                avg_r=metrics.get("avg_r", 0),
                pf=_pf(metrics.get("profit_factor")),
                dd=metrics.get("max_drawdown", 0),
                delta=metrics.get("delta_total_r_vs_baseline", 0),
                delta_current=metrics.get("delta_total_r_vs_current_policy", 0),
                confidence=metrics.get("confidence", "LOW"),
            )
        )
    lines.extend(["", "## Contexts que más mejoran/empeoran", ""])
    for layer in layers:
        improved = layer.get("top_improved_contexts", [])
        worsened = layer.get("top_worsened_contexts", [])
        lines.append(f"### {layer.get('layer')}")
        lines.append(f"- Mejoran: {_format_contexts(improved)}")
        lines.append(f"- Empeoran: {_format_contexts(worsened)}")
        lines.append(f"- Top allowed: {_format_contexts(layer.get('top_allowed_contexts', []))}")
        lines.append(f"- Top blocked: {_format_contexts(layer.get('top_blocked_contexts', []))}")
    return "\n".join(lines) + "\n"


def _evaluate_layers(trades: list[dict[str, Any]], signals: list[dict[str, Any]], *, cfg: BacktestConfig) -> list[dict[str, Any]]:
    layer_defs = [
        ("raw_strategy", _raw_accept),
        ("public_safety_policy", _public_safety_accept),
        ("relaxed_public_safety_v2", _relaxed_public_safety_v2_accept),
        ("public_short_canary", _public_short_canary_accept),
        ("protection_engine_shadow", lambda trade, prior, signals, cfg: _protection_accept(trade, prior, cfg)),
        ("pair_universe_filter_shadow", lambda trade, prior, signals, cfg: _pair_universe_accept(trade, prior, signals, cfg)),
        ("kill_switch_risk_guard", _kill_switch_accept),
    ]
    layers = []
    for name, evaluator in layer_defs:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        executed_prior: list[dict[str, Any]] = []
        history_prior: list[dict[str, Any]] = []
        for trade in trades:
            trade_for_eval = {**trade, "_history_prior": list(history_prior)}
            decision = evaluator(trade_for_eval, executed_prior, signals, cfg)
            row = {
                "trade": trade,
                "accepted": bool(decision["accepted"]),
                "reasons": list(decision.get("reasons", [])),
                "details": _dict(decision.get("details")),
            }
            rows.append(row)
            if row["accepted"]:
                accepted.append(trade)
                executed_prior.append(trade)
            else:
                rejected.append(trade)
            history_prior.append(trade)
        metrics = _metrics(accepted)
        metrics.update(
            {
                "trades_evaluated": len(trades),
                "trades_accepted": len(accepted),
                "trades_rejected": len(rejected),
                "rejection_reasons": dict(Counter(reason for row in rows for reason in row["reasons"])),
            }
        )
        layers.append(
            {
                "layer": name,
                "rows": rows,
                "accepted_trades": accepted,
                "rejected_trades": rejected,
                "metrics": metrics,
            }
        )
    return layers


def _raw_accept(trade: dict[str, Any], prior: list[dict[str, Any]], signals: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    return {"accepted": True, "reasons": [], "details": {}}


def _public_safety_accept(trade: dict[str, Any], prior: list[dict[str, Any]], signals: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    return _policy_accept(trade, canary_enabled=False, cfg=cfg)


def _relaxed_public_safety_v2_accept(trade: dict[str, Any], prior: list[dict[str, Any]], signals: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    policy = evaluate_relaxed_public_safety_v2(
        trade=trade,
        history=trade.get("_history_prior", []),
        min_rr=1.5,
        min_context_sample=5,
    )
    return {
        "accepted": bool(policy.get("public_allowed")),
        "reasons": list(policy.get("block_reasons", [])),
        "details": policy,
    }


def _public_short_canary_accept(trade: dict[str, Any], prior: list[dict[str, Any]], signals: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    return _policy_accept(trade, canary_enabled=True, cfg=cfg)


def _policy_accept(trade: dict[str, Any], *, canary_enabled: bool, cfg: BacktestConfig) -> dict[str, object]:
    context = _policy_context(trade)
    signal = SimpleNamespace(decision=trade["direction"], symbol=trade["symbol"])
    evaluation = SimpleNamespace(setup_type=trade["setup_type"], setup_score=trade.get("score"), total_score=trade.get("score"), decision_trace=[])
    policy = evaluate_public_safety_policy(
        signal=signal,
        evaluation_or_decision=evaluation,
        setup_context=context,
        public_short_canary_config=PublicShortCanaryConfig(enabled=canary_enabled, min_score=cfg.canary_min_score),
    )
    return {
        "accepted": bool(policy.get("public_allowed")),
        "reasons": list(policy.get("block_reasons", [])),
        "details": policy,
    }


def _protection_accept(trade: dict[str, Any], prior: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    reasons: list[str] = []
    timestamp = trade["timestamp"]
    symbol = trade["symbol"]
    same_symbol_losses = [
        item for item in prior
        if item["symbol"] == symbol
        and float(item["result_r"]) < 0
        and timestamp - item["timestamp"] <= timedelta(hours=cfg.protection_symbol_loss_cooldown_hours)
    ]
    if same_symbol_losses:
        reasons.append("symbol_loss_cooldown")
    recent = [item for item in prior if timestamp - item["timestamp"] <= timedelta(days=cfg.protection_max_drawdown_lookback_days)]
    if sum(float(item["result_r"]) for item in recent) <= -abs(cfg.protection_max_drawdown_guard_r):
        reasons.append("max_drawdown_guard")
    context_matches = [
        item for item in prior
        if timestamp - item["timestamp"] <= timedelta(days=cfg.protection_low_profit_lookback_days)
        and _context_key(item) == _context_key(trade)
    ]
    if len(context_matches) >= cfg.protection_low_profit_min_trades:
        avg_r = sum(float(item["result_r"]) for item in context_matches) / len(context_matches)
        if avg_r <= cfg.protection_low_profit_min_avg_r:
            reasons.append("low_profit_context_lock")
    if str(trade.get("session", "")).upper() == "NEW_YORK":
        reasons.append("toxic_context_new_york")
    if str(trade.get("market_regime", "")).upper() == "HIGH_VOLATILITY" and trade["direction"] == "long":
        reasons.append("toxic_context_high_volatility_long")
    return {"accepted": not reasons, "reasons": reasons, "details": {"protection_triggered": bool(reasons)}}


def _pair_universe_accept(
    trade: dict[str, Any],
    prior: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    cfg: BacktestConfig,
) -> dict[str, object]:
    timestamp = trade["timestamp"]
    symbol = trade["symbol"]
    reasons: list[str] = []
    recent_same_symbol = [
        item for item in prior
        if item["symbol"] == symbol
        and timestamp - item["timestamp"] <= timedelta(days=cfg.pair_universe_performance_lookback_days)
    ]
    if len(recent_same_symbol) >= cfg.pair_universe_performance_min_trades:
        avg_r = sum(float(item["result_r"]) for item in recent_same_symbol) / len(recent_same_symbol)
        if avg_r <= cfg.pair_universe_min_recent_avg_r:
            reasons.append("recent_performance_too_negative")
    recent_rejections = _recent_symbol_rejections(symbol, signals, timestamp)
    if recent_rejections >= 5:
        reasons.append("too_many_recent_rejections")
    return {
        "accepted": not reasons,
        "reasons": reasons,
        "details": {"recent_rejections": recent_rejections},
    }


def _kill_switch_accept(trade: dict[str, Any], prior: list[dict[str, Any]], signals: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, object]:
    timestamp = trade["timestamp"]
    reasons: list[str] = []
    day_start = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    daily_r = sum(float(item["result_r"]) for item in prior if item["timestamp"] >= day_start)
    if daily_r <= -abs(cfg.max_daily_loss_r):
        reasons.append("daily_loss_limit")
    weekly_start = timestamp - timedelta(days=7)
    weekly_r = sum(float(item["result_r"]) for item in prior if item["timestamp"] >= weekly_start)
    if weekly_r <= -abs(cfg.max_weekly_drawdown_r):
        reasons.append("weekly_drawdown_limit")
    if _consecutive_losses(prior) >= cfg.max_consecutive_losses:
        reasons.append("consecutive_losses_limit")
    last_loss = next((item for item in reversed(prior) if float(item["result_r"]) < 0), None)
    if last_loss and timestamp < last_loss["timestamp"] + timedelta(hours=cfg.kill_switch_cooldown_hours):
        reasons.append("cooldown_active")
    return {"accepted": not reasons, "reasons": _dedupe(reasons), "details": {"daily_r": round(daily_r, 4), "weekly_r": round(weekly_r, 4)}}


def _metrics(trades: list[dict[str, Any]]) -> dict[str, object]:
    values = [float(item["result_r"]) for item in trades]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    max_drawdown, current_drawdown = _drawdowns(values)
    return {
        "total_r": round(sum(values), 4),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0),
        "max_drawdown": round(max_drawdown, 4),
        "current_drawdown": round(current_drawdown, 4),
        "wins": len(wins),
        "losses": len(losses),
        "sample_size": len(values),
        "confidence": _confidence(len(values)),
    }


def _context_delta_rows(trades: list[dict[str, Any]], *, improvement: bool) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        for dimension in ("session", "direction", "setup_type", "market_regime", "entry_context", "trade_location"):
            grouped[(dimension, str(trade.get(dimension) or "UNKNOWN"))].append(trade)
    rows = []
    for (dimension, value), items in grouped.items():
        total_r = round(sum(float(item["result_r"]) for item in items), 4)
        if improvement and total_r >= 0:
            continue
        if not improvement and total_r <= 0:
            continue
        rows.append(
            {
                "dimension": dimension,
                "value": value,
                "sample_size": len(items),
                "total_r": total_r,
                "impact_r": round(abs(total_r), 4),
                "confidence": _confidence(len(items)),
            }
        )
    return sorted(rows, key=lambda item: float(item["impact_r"]), reverse=True)[:5]


def _context_rank_rows(trades: list[dict[str, Any]], *, best: bool) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        for dimension in ("session", "direction", "setup_type", "market_regime", "entry_context", "trade_location"):
            grouped[(dimension, str(trade.get(dimension) or "UNKNOWN"))].append(trade)
    rows = []
    for (dimension, value), items in grouped.items():
        metrics = _metrics(items)
        rows.append(
            {
                "dimension": dimension,
                "value": value,
                "sample_size": len(items),
                "total_r": metrics["total_r"],
                "winrate": metrics["winrate"],
                "avg_r": metrics["avg_r"],
                "profit_factor": metrics["profit_factor"],
                "confidence": metrics["confidence"],
            }
        )
    return sorted(rows, key=lambda item: (float(item["total_r"]), float(item["avg_r"])), reverse=best)[:5]


def _public_layer(layer: dict[str, Any]) -> dict[str, object]:
    metrics = dict(layer["metrics"])
    metrics["top_rejection_reasons"] = _top_rejection_reasons(metrics.get("rejection_reasons", {}))
    return {
        "layer": layer["layer"],
        "metrics": metrics,
        "top_improved_contexts": layer.get("top_improved_contexts", []),
        "top_worsened_contexts": layer.get("top_worsened_contexts", []),
        "top_allowed_contexts": layer.get("top_allowed_contexts", []),
        "top_blocked_contexts": layer.get("top_blocked_contexts", []),
    }


def _write_summary_csv(path: Path, layers: list[dict[str, Any]], *, cfg: BacktestConfig) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for layer in layers:
            metrics = dict(layer["metrics"])
            row = {
                "layer": layer["layer"],
                "mode": cfg.mode,
                "trades_evaluated": metrics.get("trades_evaluated", 0),
                "trades_accepted": metrics.get("trades_accepted", 0),
                "trades_rejected": metrics.get("trades_rejected", 0),
                "total_r": metrics.get("total_r", 0),
                "winrate": metrics.get("winrate", 0),
                "avg_r": metrics.get("avg_r", 0),
                "profit_factor": metrics.get("profit_factor", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "current_drawdown": metrics.get("current_drawdown", 0),
                "delta_total_r_vs_baseline": metrics.get("delta_total_r_vs_baseline", 0),
                "delta_winrate_vs_baseline": metrics.get("delta_winrate_vs_baseline", 0),
                "delta_total_r_vs_current_policy": metrics.get("delta_total_r_vs_current_policy", 0),
                "delta_accepted_vs_current_policy": metrics.get("delta_accepted_vs_current_policy", 0),
                "sample_size": metrics.get("sample_size", 0),
                "confidence": metrics.get("confidence", "LOW"),
                "top_rejection_reasons": json.dumps(_top_rejection_reasons(metrics.get("rejection_reasons", {})), ensure_ascii=False),
                "top_allowed_contexts": json.dumps(layer.get("top_allowed_contexts", []), ensure_ascii=False),
                "top_blocked_contexts": json.dumps(layer.get("top_blocked_contexts", []), ensure_ascii=False),
            }
            writer.writerow(row)


def _policy_context(trade: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": trade["symbol"],
        "direction": trade["direction"],
        "score": trade.get("score") or 0.0,
        "setup_type": trade["setup_type"],
        "market_regime": trade["market_regime"],
        "session": trade["session"],
        "entry_context": trade["entry_context"],
        "trade_location": trade["trade_location"],
        "warnings": trade.get("warnings", []),
        "avoidance_warnings": trade.get("warnings", []),
        "penalties": trade.get("penalties", []),
        "edge_activation_mode": True,
        "short_shadow_mode": True,
    }


def _recent_symbol_rejections(symbol: str, signals: list[dict[str, Any]], timestamp: datetime) -> int:
    start = timestamp - timedelta(hours=24)
    count = 0
    for row in signals:
        ts = _parse_datetime(str(row.get("timestamp") or row.get("created_at") or ""))
        if ts is None or not (start <= ts < timestamp):
            continue
        if str(row.get("symbol") or "").upper() != symbol:
            continue
        if str(row.get("status") or "").lower() in {"rejected", "no_trade"}:
            count += 1
    return count


def _consecutive_losses(prior: list[dict[str, Any]]) -> int:
    count = 0
    for item in reversed(prior):
        if float(item["result_r"]) < 0:
            count += 1
        else:
            break
    return count


def _context_key(trade: dict[str, Any]) -> str:
    return "|".join(
        [
            str(trade.get("symbol") or "").upper(),
            str(trade.get("direction") or "").lower(),
            str(trade.get("setup_type") or "").upper(),
            str(trade.get("market_regime") or "").upper(),
            str(trade.get("session") or "").upper(),
            str(trade.get("entry_context") or "").upper(),
            str(trade.get("trade_location") or ""),
        ]
    )


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _drawdowns(values: list[float]) -> tuple[float, float]:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return max_dd, cumulative - peak


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _top_rejection_reasons(reasons: object) -> list[dict[str, object]]:
    if not isinstance(reasons, dict):
        return []
    counter = Counter({str(key): int(value) for key, value in reasons.items()})
    return [{"reason": key, "count": count} for key, count in counter.most_common(5)]


def _format_contexts(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "sin datos"
    output = []
    for row in rows[:3]:
        if isinstance(row, dict):
            impact = row.get("impact_r", row.get("total_r", 0))
            output.append(f"{row.get('dimension')}:{row.get('value')} ({impact}R, n={row.get('sample_size')})")
    return ", ".join(output) if output else "sin datos"


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run-backtest-runner")
    parser.add_argument("--mode", default="shadow", choices=["shadow"])
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_backtest_runner(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        config=BacktestConfig(mode=args.mode, min_trades=max(1, args.min_trades)),
    )
    print(format_backtest_runner_summary(result["report"]))
    print(f"JSON: {result['json_path']}")
    print(f"CSV: {result['csv_path']}")
    print(f"Summary: {result['summary_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
