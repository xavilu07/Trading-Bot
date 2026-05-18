from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ACTIONS = ("PRIORITIZE", "ALLOW", "CAUTION", "WOULD_BLOCK")
CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "win", "loss"}
WIN_STATUSES = {"tp2_hit", "tp_hit", "win"}


def load_performance_gate_events(scheduler_window_path: Path) -> list[dict[str, object]]:
    if not scheduler_window_path.exists():
        return []
    try:
        raw = json.loads(scheduler_window_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []

    events: list[dict[str, object]] = []
    for cycle in raw:
        if not isinstance(cycle, dict):
            continue
        for result in cycle.get("results", []):
            if not isinstance(result, dict):
                continue
            gate = result.get("performance_gate")
            if not isinstance(gate, dict):
                pattern_memory = result.get("pattern_memory")
                gate = pattern_memory.get("performance_gate") if isinstance(pattern_memory, dict) else None
            if not isinstance(gate, dict):
                continue
            signal = result.get("signal")
            signal = signal if isinstance(signal, dict) else {}
            gate_context = gate.get("context")
            gate_context = gate_context if isinstance(gate_context, dict) else {}
            events.append(
                {
                    "symbol": result.get("symbol") or signal.get("symbol"),
                    "direction": signal.get("decision") or gate_context.get("direction"),
                    "setup_type": gate_context.get("setup_type") or _nested(result, "setup_context", "setup_type"),
                    "dedupe_key": signal.get("dedupe_key"),
                    "created_at": signal.get("created_at"),
                    "action": str(gate.get("action") or "UNKNOWN").upper(),
                    "would_block": bool(gate.get("would_block")),
                    "would_prioritize": bool(gate.get("would_prioritize")),
                    "confidence": str(gate.get("confidence") or "LOW").upper(),
                    "reasons": gate.get("reasons", []),
                    "risks": gate.get("risks", []),
                    "scores": gate.get("scores", {}),
                    "gate": gate,
                }
            )
    return events


def load_closed_paper_trades(data_path: Path) -> list[dict[str, object]]:
    trades_path = data_path / "paper_trading"
    if not trades_path.exists():
        return []

    trades: list[dict[str, object]] = []
    for csv_path in sorted(trades_path.glob("*.csv")):
        if not csv_path.is_file():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                status = str(row.get("status") or row.get("outcome") or "").strip().lower()
                result_r = _to_float(row.get("result_r") or row.get("r_result") or row.get("r"))
                if status not in CLOSED_STATUSES or result_r is None:
                    continue
                item: dict[str, object] = dict(row)
                item["status"] = status
                item["result_r"] = result_r
                item["source_csv"] = str(csv_path)
                trades.append(item)
    return trades


def match_gate_events_to_trades(
    events: list[dict[str, object]],
    trades: list[dict[str, object]],
) -> list[dict[str, object]]:
    trades_by_dedupe: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        dedupe_key = str(trade.get("dedupe_key") or "")
        if not dedupe_key:
            continue
        trades_by_dedupe[_base_trade_dedupe_key(dedupe_key)].append(trade)

    matched = []
    used_trade_ids: set[str] = set()
    for event in events:
        trade = _match_by_dedupe(event, trades_by_dedupe, used_trade_ids)
        if trade is None:
            trade = _match_by_attributes(event, trades, used_trade_ids)
        matched.append({**event, "trade": trade, "matched_outcome": trade is not None})
        if trade is not None:
            used_trade_ids.add(_trade_identity(trade))
    return matched


def analyze_performance_gate(
    *,
    data_path: Path,
    scheduler_window_path: Path,
) -> dict[str, object]:
    events = load_performance_gate_events(scheduler_window_path)
    trades = load_closed_paper_trades(data_path)
    matched_events = match_gate_events_to_trades(events, trades)
    by_action = {action: [] for action in ACTIONS}
    for event in matched_events:
        action = str(event.get("action") or "UNKNOWN").upper()
        if action in by_action:
            by_action[action].append(event)

    action_counts = Counter(str(event.get("action") or "UNKNOWN").upper() for event in events)
    metrics_by_action = {
        action: _metrics_for_events(action_events)
        for action, action_events in by_action.items()
    }
    would_block = metrics_by_action["WOULD_BLOCK"]
    prioritize = metrics_by_action["PRIORITIZE"]
    non_prioritize_events = [
        event
        for action, action_events in by_action.items()
        if action != "PRIORITIZE"
        for event in action_events
    ]
    non_prioritize = _metrics_for_events(non_prioritize_events)

    return {
        "source": {
            "scheduler_window_path": str(scheduler_window_path),
            "data_path": str(data_path),
        },
        "total_gate_events": len(events),
        "matched_outcomes": sum(1 for event in matched_events if event.get("matched_outcome")),
        "unmatched_outcomes": sum(1 for event in matched_events if not event.get("matched_outcome")),
        "action_counts": {action: action_counts.get(action, 0) for action in ACTIONS},
        "metrics_by_action": metrics_by_action,
        "would_block_impact": {
            "would_block_count": action_counts.get("WOULD_BLOCK", 0),
            "matched_closed_trades": would_block["closed_trades"],
            "losses_avoided": would_block["losses"],
            "loss_r_avoided": round(abs(min(0.0, would_block["total_r"])), 4),
            "winning_trades_would_have_been_blocked": would_block["wins"],
            "winning_r_would_have_been_blocked": round(would_block["gross_profit"], 4),
        },
        "prioritize_vs_rest": {
            "prioritize": prioritize,
            "non_prioritize": non_prioritize,
            "prioritize_has_better_avg_r": _nullable_gt(prioritize["avg_r"], non_prioritize["avg_r"]),
            "prioritize_has_better_winrate": _nullable_gt(prioritize["winrate"], non_prioritize["winrate"]),
            "prioritize_has_better_profit_factor": _nullable_gt(
                prioritize["profit_factor"],
                non_prioritize["profit_factor"],
            ),
        },
    }


def format_analysis(result: dict[str, object]) -> str:
    metrics = result.get("metrics_by_action", {})
    if not isinstance(metrics, dict):
        metrics = {}
    lines = [
        "Performance Gate Impact",
        f"- Gate events: {result.get('total_gate_events', 0)}",
        f"- Matched closed outcomes: {result.get('matched_outcomes', 0)}",
        f"- Unmatched outcomes: {result.get('unmatched_outcomes', 0)}",
        "",
        "Actions",
    ]
    action_counts = result.get("action_counts", {})
    action_counts = action_counts if isinstance(action_counts, dict) else {}
    for action in ACTIONS:
        item = metrics.get(action, {})
        item = item if isinstance(item, dict) else {}
        lines.append(
            f"- {action}: count {action_counts.get(action, 0)}, "
            f"closed {item.get('closed_trades', 0)}, winrate {_fmt_pct(item.get('winrate'))}, "
            f"avgR {_fmt_r(item.get('avg_r'))}, totalR {_fmt_r(item.get('total_r'))}, "
            f"PF {_fmt_pf(item.get('profit_factor'))}"
        )

    would_block = result.get("would_block_impact", {})
    would_block = would_block if isinstance(would_block, dict) else {}
    prioritize = result.get("prioritize_vs_rest", {})
    prioritize = prioritize if isinstance(prioritize, dict) else {}
    lines.extend(
        [
            "",
            "WOULD_BLOCK impact",
            f"- Losses avoided: {would_block.get('losses_avoided', 0)}",
            f"- Loss R avoided: {_fmt_r(would_block.get('loss_r_avoided'))}",
            f"- Winning trades blocked: {would_block.get('winning_trades_would_have_been_blocked', 0)}",
            f"- Winning R blocked: {_fmt_r(would_block.get('winning_r_would_have_been_blocked'))}",
            "",
            "PRIORITIZE vs rest",
            f"- Better avgR: {_yes_no(prioritize.get('prioritize_has_better_avg_r'))}",
            f"- Better winrate: {_yes_no(prioritize.get('prioritize_has_better_winrate'))}",
            f"- Better profit factor: {_yes_no(prioritize.get('prioritize_has_better_profit_factor'))}",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="analyze-performance-gate")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--scheduler-window", default="data/scheduler_diagnostic_window.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_performance_gate(
        data_path=Path(args.data_path),
        scheduler_window_path=Path(args.scheduler_window),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_analysis(result))
    return 0


def _metrics_for_events(events: list[dict[str, object]]) -> dict[str, object]:
    trades = [event["trade"] for event in events if isinstance(event.get("trade"), dict)]
    r_values = [float(trade["result_r"]) for trade in trades]
    wins = [trade for trade in trades if str(trade.get("status")) in WIN_STATUSES or float(trade["result_r"]) > 0]
    losses = [trade for trade in trades if float(trade["result_r"]) < 0]
    gross_profit = sum(value for value in r_values if value > 0)
    gross_loss = abs(sum(value for value in r_values if value < 0))
    return {
        "gate_events": len(events),
        "closed_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(trades) * 100, 2) if trades else None,
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "total_r": round(sum(r_values), 4) if r_values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (None if not trades else float("inf")),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
    }


def _match_by_dedupe(
    event: dict[str, object],
    trades_by_dedupe: dict[str, list[dict[str, object]]],
    used_trade_ids: set[str],
) -> dict[str, object] | None:
    dedupe_key = str(event.get("dedupe_key") or "")
    if not dedupe_key:
        return None
    for trade_key, candidates in trades_by_dedupe.items():
        if not (trade_key == dedupe_key or trade_key.startswith(f"{dedupe_key}|")):
            continue
        for trade in candidates:
            if _trade_identity(trade) not in used_trade_ids:
                return trade
    return None


def _match_by_attributes(
    event: dict[str, object],
    trades: list[dict[str, object]],
    used_trade_ids: set[str],
) -> dict[str, object] | None:
    symbol = str(event.get("symbol") or "").upper()
    direction = str(event.get("direction") or "").lower()
    setup_type = str(event.get("setup_type") or "").upper()
    for trade in trades:
        if _trade_identity(trade) in used_trade_ids:
            continue
        if symbol and str(trade.get("symbol") or "").upper() != symbol:
            continue
        if direction in {"long", "short"} and str(trade.get("direction") or "").lower() != direction:
            continue
        if setup_type and str(trade.get("setup_type") or "").upper() != setup_type:
            continue
        return trade
    return None


def _base_trade_dedupe_key(dedupe_key: str) -> str:
    if dedupe_key.endswith("|paper"):
        return dedupe_key[: -len("|paper")]
    return dedupe_key


def _trade_identity(trade: dict[str, object]) -> str:
    return str(trade.get("trade_id") or trade.get("dedupe_key") or id(trade))


def _nested(value: object, *keys: str) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _nullable_gt(left: object, right: object) -> bool | None:
    left_value = _to_float(left)
    right_value = _to_float(right)
    if left_value is None or right_value is None:
        return None
    return left_value > right_value


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_pct(value: object) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric}%"


def _fmt_r(value: object) -> str:
    numeric = _to_float(value)
    return "n/a" if numeric is None else f"{numeric:.4f}R"


def _fmt_pf(value: object) -> str:
    numeric = _to_float(value)
    if numeric is None:
        return "n/a"
    if numeric == float("inf"):
        return "inf"
    return f"{numeric:.4f}"


def _yes_no(value: object) -> str:
    if value is None:
        return "n/a"
    return "yes" if value is True else "no"


if __name__ == "__main__":
    raise SystemExit(main())
