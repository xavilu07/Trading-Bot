from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_signals.application.policies.public_safety_policy import evaluate_public_safety_policy
from trading_signals.application.policies.relaxed_public_safety_v2 import evaluate_relaxed_public_safety_v2
from trading_signals.data.canonical_trade_source import compute_trade_metrics, load_canonical_closed_trades


CLASSIFICATIONS = {"CONFIRMED_EDGE", "POSSIBLE_EDGE", "NO_EDGE", "TOXIC_CONTEXT"}
CSV_FIELDS = [
    "generated_at",
    "hypothesis",
    "category",
    "classification",
    "survives",
    "sample_size",
    "total_r",
    "winrate",
    "avg_r",
    "profit_factor",
    "max_drawdown",
    "current_drawdown",
    "confidence",
    "notes",
]


def recalculate_post_consistency_edge(
    *,
    data_path: Path = Path("data"),
    min_trades: int = 5,
) -> dict[str, Any]:
    trades = load_canonical_closed_trades(data_path)
    rows = _hypothesis_rows(trades, min_trades=min_trades)
    grouped = {
        "confirmed_edge": [row for row in rows if row["classification"] == "CONFIRMED_EDGE"],
        "possible_edge": [row for row in rows if row["classification"] == "POSSIBLE_EDGE"],
        "no_edge": [row for row in rows if row["classification"] == "NO_EDGE"],
        "toxic_context": [row for row in rows if row["classification"] == "TOXIC_CONTEXT"],
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "data/paper_trading/trades.csv",
        "records_analyzed": len(trades),
        "min_trades": min_trades,
        "canonical_metrics": compute_trade_metrics(trades),
        "hypotheses": rows,
        "summary": {
            key: len(value)
            for key, value in grouped.items()
        },
        "hypotheses_that_survive": [
            {
                "hypothesis": row["hypothesis"],
                "classification": row["classification"],
                "sample_size": row["sample_size"],
                "total_r": row["total_r"],
                "profit_factor": row["profit_factor"],
            }
            for row in rows
            if row["survives"]
        ],
        "london_short": _find(rows, "LONDON_SHORT"),
        "high_volatility_long": _find(rows, "HIGH_VOLATILITY_LONG"),
        "context_toxicity": [row for row in rows if row["category"] == "context_toxicity"],
        "shadow_send_current_reject": _find(rows, "SHADOW_SEND_CURRENT_REJECT"),
    }


def write_post_consistency_edge_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "post_consistency_edge_recalc.json"
    csv_path = reports_path / "post_consistency_edge_recalc.csv"
    md_path = reports_path / "post_consistency_edge_recalc_summary.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_csv(csv_path, result.get("hypotheses", []), result.get("generated_at"))
    md_path.write_text(format_post_consistency_edge_summary(result), encoding="utf-8")
    return {"json_path": json_path, "csv_path": csv_path, "summary_path": md_path}


def format_post_consistency_edge_summary(result: dict[str, Any]) -> str:
    metrics = _dict(result.get("canonical_metrics"))
    lines = [
        "# Post-Consistency Edge Recalculation",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Dataset: `{result.get('dataset')}`",
        f"- Records analyzed: {result.get('records_analyzed', 0)}",
        f"- Min trades: {result.get('min_trades', 0)}",
        f"- Canonical Total R: {metrics.get('total_r', 0)}",
        f"- Canonical WR: {metrics.get('winrate', 0)}%",
        f"- Canonical PF: {metrics.get('profit_factor', 0)}",
        "",
        "## Hypotheses",
        "",
        "| Hypothesis | Classification | n | Total R | WR | AvgR | PF | Notes |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in _list(result.get("hypotheses")):
        lines.append(
            "| {hypothesis} | {classification} | {sample} | {total_r} | {wr}% | {avg_r} | {pf} | {notes} |".format(
                hypothesis=row.get("hypothesis"),
                classification=row.get("classification"),
                sample=row.get("sample_size"),
                total_r=row.get("total_r"),
                wr=row.get("winrate"),
                avg_r=row.get("avg_r"),
                pf=_pf(row.get("profit_factor")),
                notes=str(row.get("notes") or "").replace("|", "/"),
            )
        )
    lines.extend(["", "## Surviving Hypotheses", ""])
    survivors = _list(result.get("hypotheses_that_survive"))
    if survivors:
        for row in survivors:
            lines.append(
                f"- {row.get('hypothesis')}: {row.get('classification')} | "
                f"n={row.get('sample_size')} | TotalR={row.get('total_r')} | PF={_pf(row.get('profit_factor'))}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Interpretation", ""])
    lines.append("- CONFIRMED_EDGE: muestra suficiente y edge positivo claro.")
    lines.append("- POSSIBLE_EDGE: edge positivo, pero con muestra limitada o señal estadística moderada.")
    lines.append("- NO_EDGE: no hay evidencia positiva suficiente.")
    lines.append("- TOXIC_CONTEXT: rendimiento negativo con muestra mínima suficiente.")
    return "\n".join(lines).rstrip() + "\n"


def _hypothesis_rows(trades: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    definitions: list[tuple[str, str, list[dict[str, Any]], str]] = [
        ("LONDON_SHORT", "london_short", _where(trades, session="LONDON", direction="short"), "London short edge after canonical consistency."),
        (
            "HIGH_VOLATILITY_LONG",
            "high_volatility_long",
            _where(trades, market_regime="HIGH_VOLATILITY", direction="long"),
            "Checks whether high-volatility long remains toxic or has edge.",
        ),
        (
            "HIGH_VOLATILITY_SHORT",
            "high_volatility_short",
            _where(trades, market_regime="HIGH_VOLATILITY", direction="short"),
            "Checks whether high-volatility short has hidden edge after canonical consistency.",
        ),
        (
            "CONTEXT_CHOPPY_RANGE",
            "context_toxicity",
            _where(trades, entry_context="CHOPPY_RANGE"),
            "Context Toxicity target: entry_context=CHOPPY_RANGE.",
        ),
        (
            "CONTEXT_HIGH_VOLATILITY",
            "context_toxicity",
            _where(trades, market_regime="HIGH_VOLATILITY"),
            "Context Toxicity target: market_regime=HIGH_VOLATILITY.",
        ),
        (
            "CONTEXT_SETUP_UNKNOWN",
            "context_toxicity",
            _where(trades, setup_type="UNKNOWN"),
            "Context Toxicity target: setup_type=UNKNOWN.",
        ),
        (
            "CONTEXT_SESSION_UNKNOWN",
            "context_toxicity",
            _where(trades, session="UNKNOWN"),
            "Context Toxicity target: session=UNKNOWN.",
        ),
        (
            "CONTEXT_TRADE_LOCATION_UNKNOWN",
            "context_toxicity",
            _where(trades, trade_location="UNKNOWN"),
            "Context Toxicity target: trade_location=UNKNOWN.",
        ),
    ]
    shadow_rows = _shadow_send_current_reject(trades)
    definitions.append(
        (
            "SHADOW_SEND_CURRENT_REJECT",
            "shadow_vs_current",
            shadow_rows,
            "Relaxed shadow policy allowed while current public policy rejected, evaluated only on canonical trades.",
        )
    )
    rows = [_row_for_hypothesis(name, category, items, notes, min_trades=min_trades) for name, category, items, notes in definitions]
    rows.extend(_context_breakdown_rows(trades, min_trades=min_trades))
    return rows


def _context_breakdown_rows(trades: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    focused = {
        "CHOPPY_RANGE_SHORT": _where(trades, entry_context="CHOPPY_RANGE", direction="short"),
        "CHOPPY_RANGE_LONG": _where(trades, entry_context="CHOPPY_RANGE", direction="long"),
        "LONDON_SHORT_PULLBACK_MAIN_SIGNAL": _where(trades, session="LONDON", direction="short", entry_context="PULLBACK", setup_type="MAIN_SIGNAL"),
    }
    for name, items in focused.items():
        output.append(_row_for_hypothesis(name, "context_breakdown", items, "Focused context breakdown.", min_trades=min_trades))
    return output


def _row_for_hypothesis(
    hypothesis: str,
    category: str,
    trades: list[dict[str, Any]],
    notes: str,
    *,
    min_trades: int,
) -> dict[str, Any]:
    metrics = compute_trade_metrics(trades)
    classification = _classify(metrics, min_trades=min_trades)
    return {
        "hypothesis": hypothesis,
        "category": category,
        "classification": classification,
        "survives": classification in {"CONFIRMED_EDGE", "POSSIBLE_EDGE", "TOXIC_CONTEXT"},
        "sample_size": metrics["closed_trades"],
        "total_r": metrics["total_r"],
        "winrate": metrics["winrate"],
        "avg_r": metrics["avg_r"],
        "profit_factor": metrics["profit_factor"],
        "max_drawdown": metrics["max_drawdown"],
        "current_drawdown": metrics["current_drawdown"],
        "confidence": _confidence(int(metrics["closed_trades"])),
        "notes": notes,
    }


def _classify(metrics: dict[str, Any], *, min_trades: int) -> str:
    sample = int(metrics.get("closed_trades") or 0)
    total_r = float(metrics.get("total_r") or 0.0)
    avg_r = float(metrics.get("avg_r") or 0.0)
    winrate = float(metrics.get("winrate") or 0.0)
    profit_factor = float(metrics.get("profit_factor") or 0.0)
    if sample == 0:
        return "NO_EDGE"
    if sample >= max(10, min_trades * 2) and total_r > 0 and avg_r > 0 and winrate >= 50 and profit_factor >= 1.2:
        return "CONFIRMED_EDGE"
    if sample >= min_trades and total_r < 0 and avg_r < 0 and (winrate < 40 or profit_factor < 1.0):
        return "TOXIC_CONTEXT"
    if sample >= min_trades and total_r > 0 and avg_r > 0 and (profit_factor > 1.0 or winrate >= 45):
        return "POSSIBLE_EDGE"
    return "NO_EDGE"


def _shadow_send_current_reject(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for trade in trades:
        current = _current_policy(trade)
        relaxed = evaluate_relaxed_public_safety_v2(trade=trade, history=history, min_rr=1.5, min_context_sample=5)
        if not current.get("public_allowed") and relaxed.get("public_allowed"):
            output.append(
                {
                    **trade,
                    "current_policy_block_reasons": current.get("block_reasons", []),
                    "shadow_policy_reason": relaxed.get("warnings", []) or ["relaxed_public_safety_v2_allowed"],
                }
            )
        history.append(trade)
    return output


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


def _where(trades: list[dict[str, Any]], **criteria: str) -> list[dict[str, Any]]:
    return [
        trade
        for trade in trades
        if all(_norm(trade.get(key), key=key) == _norm(value, key=key) for key, value in criteria.items())
    ]


def _norm(value: object, *, key: str) -> str:
    text = str(value or "").strip()
    if key == "direction":
        return text.lower()
    if key == "trade_location":
        return text
    return text.upper() if text else "UNKNOWN"


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _find(rows: list[dict[str, Any]], hypothesis: str) -> dict[str, Any]:
    return next((row for row in rows if row["hypothesis"] == hypothesis), {})


def _write_csv(path: Path, rows: object, generated_at: str | None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    output = {field: row.get(field, "") for field in CSV_FIELDS}
                    output["generated_at"] = generated_at or ""
                    writer.writerow(output)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _pf(value: object) -> object:
    return "inf" if value is None else value
