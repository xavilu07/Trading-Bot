from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_signals.application.policies.public_safety_policy import evaluate_public_safety_policy
from trading_signals.application.policies.relaxed_public_safety_v2 import evaluate_relaxed_public_safety_v2
from trading_signals.data.canonical_trade_source import compute_trade_metrics, load_canonical_closed_trades


TRADE_FIELDS = [
    "timestamp",
    "symbol",
    "session",
    "direction",
    "setup_type",
    "score",
    "entry_context",
    "market_regime",
    "trade_location",
    "rejection_reasons",
    "result_status",
    "result_r",
]

REASON_FIELDS = [
    "reason",
    "classification",
    "sample_size",
    "wins",
    "losses",
    "winrate",
    "total_r",
    "avg_r",
    "profit_factor",
    "impact_r",
    "recommendation",
]


def analyze_shadow_send_current_reject(
    *,
    data_path: Path = Path("data"),
    min_trades: int = 5,
) -> dict[str, Any]:
    trades = load_canonical_closed_trades(data_path)
    candidates = _shadow_send_current_reject_trades(trades)
    reason_rows = _reason_impact_rows(candidates, min_trades=min_trades)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "data/paper_trading/trades.csv",
        "scope": "SHADOW_SEND_CURRENT_REJECT",
        "definition": "current public_safety_policy rejected while relaxed_public_safety_v2 would send",
        "records_analyzed": len(trades),
        "sample_size": len(candidates),
        "min_trades": min_trades,
        "metrics": compute_trade_metrics(candidates),
        "trades": [_trade_output(row) for row in candidates],
        "rejection_reason_impact": reason_rows,
        "top_rejection_reasons_destroying_edge": [
            row for row in reason_rows if row["total_r"] > 0
        ][:10],
        "relaxation_ranking": reason_rows,
    }


def write_shadow_send_current_reject_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "shadow_send_current_reject_deep_dive.json"
    trades_csv_path = reports_path / "shadow_send_current_reject_trades.csv"
    reasons_csv_path = reports_path / "shadow_send_current_reject_rejection_reasons.csv"
    summary_path = reports_path / "shadow_send_current_reject_summary.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_csv(trades_csv_path, result.get("trades", []), TRADE_FIELDS)
    _write_csv(reasons_csv_path, result.get("rejection_reason_impact", []), REASON_FIELDS)
    summary_path.write_text(format_shadow_send_current_reject_summary(result), encoding="utf-8")
    return {
        "json_path": json_path,
        "trades_csv_path": trades_csv_path,
        "reasons_csv_path": reasons_csv_path,
        "summary_path": summary_path,
    }


def format_shadow_send_current_reject_summary(result: dict[str, Any]) -> str:
    metrics = _dict(result.get("metrics"))
    lines = [
        "# SHADOW_SEND_CURRENT_REJECT Deep Dive",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Dataset: `{result.get('dataset')}`",
        f"- Records analyzed: {result.get('records_analyzed', 0)}",
        f"- Shadow SEND / Current REJECT trades: {result.get('sample_size', 0)}",
        f"- Total R: {metrics.get('total_r', 0)}",
        f"- Winrate: {metrics.get('winrate', 0)}%",
        f"- Profit Factor: {metrics.get('profit_factor', 0)}",
        "",
        "## Trades",
        "",
        "| Symbol | Session | Direction | Setup | Score | Rejection reasons | Status | R |",
        "|---|---|---|---|---:|---|---|---:|",
    ]
    for row in _list(result.get("trades")):
        lines.append(
            "| {symbol} | {session} | {direction} | {setup} | {score} | {reasons} | {status} | {r} |".format(
                symbol=row.get("symbol"),
                session=row.get("session"),
                direction=str(row.get("direction") or "").upper(),
                setup=row.get("setup_type"),
                score=_fmt(row.get("score")),
                reasons=str(row.get("rejection_reasons") or "").replace("|", "/"),
                status=row.get("result_status"),
                r=row.get("result_r"),
            )
        )

    lines.extend(
        [
            "",
            "## Rejection Reasons Destroying Edge",
            "",
            "| Reason | Classification | n | Total R | WR | AvgR | PF | Recommendation |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in _list(result.get("rejection_reason_impact")):
        lines.append(
            "| {reason} | {classification} | {n} | {total_r} | {wr}% | {avg_r} | {pf} | {recommendation} |".format(
                reason=row.get("reason"),
                classification=row.get("classification"),
                n=row.get("sample_size"),
                total_r=row.get("total_r"),
                wr=row.get("winrate"),
                avg_r=row.get("avg_r"),
                pf=row.get("profit_factor"),
                recommendation=row.get("recommendation"),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _shadow_send_current_reject_trades(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for trade in trades:
        current = _current_policy(trade)
        relaxed = evaluate_relaxed_public_safety_v2(trade=trade, history=history, min_rr=1.5, min_context_sample=5)
        if not current.get("public_allowed") and relaxed.get("public_allowed"):
            output.append(
                {
                    **trade,
                    "current_decision": "REJECT",
                    "shadow_decision": "SEND",
                    "current_policy_block_reasons": _dedupe(current.get("block_reasons", [])),
                    "shadow_policy_reason": relaxed.get("warnings", []) or ["relaxed_public_safety_v2_allowed"],
                }
            )
        history.append(trade)
    return output


def _reason_impact_rows(candidates: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in candidates:
        for reason in _reasons(trade):
            grouped[reason].append(trade)
    rows = []
    for reason, items in grouped.items():
        metrics = compute_trade_metrics(items)
        classification = _classify_reason(metrics, min_trades=min_trades)
        rows.append(
            {
                "reason": reason,
                "classification": classification,
                "sample_size": metrics["closed_trades"],
                "wins": metrics["wins"],
                "losses": metrics["losses"],
                "winrate": metrics["winrate"],
                "total_r": metrics["total_r"],
                "avg_r": metrics["avg_r"],
                "profit_factor": metrics["profit_factor"],
                "impact_r": metrics["total_r"],
                "recommendation": _recommendation(classification),
            }
        )
    return sorted(rows, key=lambda row: (row["classification"] != "SAFE_TO_RELAX", -float(row["total_r"]), -int(row["sample_size"])))


def _classify_reason(metrics: dict[str, Any], *, min_trades: int) -> str:
    sample = int(metrics.get("closed_trades") or 0)
    total_r = float(metrics.get("total_r") or 0.0)
    avg_r = float(metrics.get("avg_r") or 0.0)
    profit_factor = float(metrics.get("profit_factor") or 0.0)
    winrate = float(metrics.get("winrate") or 0.0)
    if sample >= min_trades and total_r > 0 and avg_r > 0 and profit_factor >= 1.2:
        return "SAFE_TO_RELAX"
    if sample >= min_trades and total_r < 0 and avg_r < 0 and (profit_factor < 1.0 or winrate < 40):
        return "NEVER_RELAX"
    return "NEED_MORE_DATA"


def _recommendation(classification: str) -> str:
    if classification == "SAFE_TO_RELAX":
        return "Candidate for controlled shadow/public relaxation; validate with forward sample first."
    if classification == "NEVER_RELAX":
        return "Keep blocked; current canonical evidence is negative."
    return "Keep in shadow; sample is not strong enough for production relaxation."


def _trade_output(trade: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": trade.get("timestamp") or trade.get("closed_at") or trade.get("opened_at"),
        "symbol": trade.get("symbol"),
        "session": trade.get("session"),
        "direction": str(trade.get("direction") or "").upper(),
        "setup_type": trade.get("setup_type"),
        "score": trade.get("score"),
        "entry_context": trade.get("entry_context"),
        "market_regime": trade.get("market_regime"),
        "trade_location": trade.get("trade_location"),
        "rejection_reasons": "|".join(_reasons(trade)),
        "result_status": trade.get("status"),
        "result_r": trade.get("result_r"),
    }


def _current_policy(trade: dict[str, Any]) -> dict[str, Any]:
    signal = SimpleNamespace(decision=trade.get("direction"), symbol=trade.get("symbol"))
    evaluation = SimpleNamespace(setup_type=trade.get("setup_type"), setup_score=trade.get("score"), total_score=trade.get("score"), decision_trace=[])
    return evaluate_public_safety_policy(
        signal=signal,
        evaluation_or_decision=evaluation,
        setup_context={
            "symbol": trade.get("symbol"),
            "direction": trade.get("direction"),
            "score": trade.get("score") or 0.0,
            "setup_type": trade.get("setup_type"),
            "market_regime": trade.get("market_regime"),
            "session": trade.get("session"),
            "entry_context": trade.get("entry_context"),
            "trade_location": trade.get("trade_location"),
            "warnings": trade.get("warnings", []),
            "avoidance_warnings": trade.get("avoidance_warnings", []),
            "penalties": trade.get("penalties", []),
            "edge_activation_mode": True,
            "short_shadow_mode": True,
        },
    )


def _reasons(trade: dict[str, Any]) -> list[str]:
    reasons = list(trade.get("current_policy_block_reasons") or [])
    if not reasons:
        reasons = list(trade.get("rejection_reasons") or [])
    return _dedupe(str(reason).strip() for reason in reasons if str(reason).strip())


def _write_csv(path: Path, rows: object, fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow({field: row.get(field, "") for field in fields})


def _dedupe(values: object) -> list[str]:
    output: list[str] = []
    for value in values if not isinstance(values, str) else [values]:
        text = str(value).strip()
        if text and text not in output:
            output.append(text)
    return output


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _fmt(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(round(float(value), 2))
    except (TypeError, ValueError):
        return str(value)
