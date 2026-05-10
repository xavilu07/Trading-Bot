from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable


def parse_log_lines(lines: Iterable[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") in {
            "module_diagnostic",
            "signal_decision_current",
            "signal_decision_parallel",
        }:
            rows.append(payload)
    return rows


def load_module_diagnostics(path: Path | None) -> list[dict[str, object]]:
    if path is None:
        return parse_log_lines(sys.stdin)
    if not path.exists():
        raise FileNotFoundError(f"No existe el log indicado: {path}")
    return parse_log_lines(path.read_text(encoding="utf-8").splitlines())


def build_summary(rows: list[dict[str, object]], *, limit: int = 5) -> dict[str, object]:
    module_status: Counter[tuple[str, bool]] = Counter()
    module_reasons: Counter[tuple[str, str]] = Counter()
    module_scores: dict[str, list[float]] = defaultdict(list)
    module_symbols: dict[str, Counter[str]] = defaultdict(Counter)
    decision_rejections: Counter[str] = Counter()
    experimental_signals: list[dict[str, object]] = []
    by_symbol: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    signal_decisions: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)

    for row in rows:
        event = str(row.get("event", ""))
        if event in {"signal_decision_current", "signal_decision_parallel"}:
            symbol = str(row.get("symbol", "UNKNOWN"))
            signal_decisions[symbol]["current" if event == "signal_decision_current" else "parallel"] = row
            continue
        module = str(row.get("module", "unknown"))
        ok = bool(row.get("ok"))
        reason = str(row.get("reason", "unknown"))
        symbol = str(row.get("symbol", "UNKNOWN"))
        score = float(row.get("score") or 0.0)
        module_status[(module, ok)] += 1
        module_reasons[(module, reason)] += 1
        module_scores[module].append(score)
        module_symbols[module][symbol] += 1
        by_symbol[symbol][module] = row
        if module == "decision_engine":
            details = row.get("details", {})
            if isinstance(details, dict):
                for rejection in details.get("rejection_reasons", []) or []:
                    decision_rejections[str(rejection)] += 1
        if module == "experimental_decision_engine":
            details = row.get("details", {})
            if isinstance(details, dict) and details.get("would_send_signal") is True:
                experimental_signals.append(
                    {
                        "symbol": symbol,
                        "direction": details.get("direction"),
                        "score": details.get("score"),
                        "original_blocking_filter": details.get("original_blocking_filter"),
                        "experimental_reason": details.get("experimental_reason"),
                    }
                )

    modules: list[dict[str, object]] = []
    for module in sorted(module_scores):
        ok_count = module_status[(module, True)]
        fail_count = module_status[(module, False)]
        reasons = [
            {"reason": reason, "count": count}
            for (reason_module, reason), count in module_reasons.most_common()
            if reason_module == module
        ][:limit]
        symbols = [
            {"symbol": symbol, "count": count}
            for symbol, count in module_symbols[module].most_common(limit)
        ]
        modules.append(
            {
                "module": module,
                "ok_true": ok_count,
                "ok_false": fail_count,
                "average_score": round(mean(module_scores[module]), 2),
                "top_reasons": reasons,
                "top_symbols": symbols,
            }
        )

    return {
        "total_module_diagnostics": len([row for row in rows if row.get("event") == "module_diagnostic"]),
        "modules": modules,
        "decision_engine_top_rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in decision_rejections.most_common(limit)
        ],
        "near_miss_candidates": build_near_miss_candidates(by_symbol, limit=limit),
        "valid_dry_run_signals": build_valid_dry_run_signals(by_symbol, limit=limit),
        "experimental_signals": sorted(
            experimental_signals,
            key=lambda item: float(item.get("score") or 0.0),
            reverse=True,
        )[:limit],
        "signal_decision_comparison": build_signal_decision_comparison(signal_decisions, limit=limit),
    }


def build_signal_decision_comparison(signal_decisions: dict[str, dict[str, dict[str, object]]], *, limit: int) -> dict[str, object]:
    matches = 0
    differs = 0
    current_reject_parallel_send_or_paper: list[dict[str, object]] = []
    current_send_parallel_reject: list[dict[str, object]] = []
    for symbol, pair in signal_decisions.items():
        current = pair.get("current")
        parallel = pair.get("parallel")
        if not current or not parallel:
            continue
        current_decision = str(current.get("decision"))
        parallel_decision = str(parallel.get("decision"))
        if current_decision == parallel_decision:
            matches += 1
        else:
            differs += 1
        payload = {
            "symbol": symbol,
            "current_decision": current_decision,
            "parallel_decision": parallel_decision,
            "current_direction": current.get("direction"),
            "parallel_direction": parallel.get("direction"),
            "current_score": current.get("total_score"),
            "parallel_score": parallel.get("total_score"),
            "parallel_rejection_reasons": parallel.get("rejection_reasons", []),
        }
        if current_decision == "REJECT" and parallel_decision in {"SEND", "PAPER_ONLY"}:
            current_reject_parallel_send_or_paper.append(payload)
        if current_decision == "SEND" and parallel_decision == "REJECT":
            current_send_parallel_reject.append(payload)
    return {
        "matches": matches,
        "differs": differs,
        "current_reject_parallel_send_or_paper": current_reject_parallel_send_or_paper[:limit],
        "current_send_parallel_reject": current_send_parallel_reject[:limit],
    }


def build_near_miss_candidates(by_symbol: dict[str, dict[str, dict[str, object]]], *, limit: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for symbol, modules in by_symbol.items():
        momentum = modules.get("momentum", {})
        decision_engine = modules.get("decision_engine", {})
        signal_builder = modules.get("signal_builder", {})
        strategy_gate = modules.get("strategy_gate", {})
        momentum_details = momentum.get("details", {}) if isinstance(momentum.get("details"), dict) else {}
        decision_details = decision_engine.get("details", {}) if isinstance(decision_engine.get("details"), dict) else {}
        signal_details = signal_builder.get("details", {}) if isinstance(signal_builder.get("details"), dict) else {}
        gate_details = strategy_gate.get("details", {}) if isinstance(strategy_gate.get("details"), dict) else {}
        body_ratio = _float_or_none(momentum_details.get("body_ratio"))
        volume_ratio = _float_or_none(momentum_details.get("volume_ratio"))
        rsi = _float_or_none(momentum_details.get("rsi"))
        decision = str(decision_details.get("decision", "REJECT"))
        if body_ratio is None or volume_ratio is None or rsi is None:
            continue
        if body_ratio >= 0.25 and volume_ratio >= 1.2 and decision != "SEND":
            rejection_reasons = decision_details.get("rejection_reasons", []) or []
            principal_reason = str(rejection_reasons[0]) if rejection_reasons else str(decision_engine.get("reason", "unknown"))
            candidates.append(
                {
                    "symbol": symbol,
                    "direction": signal_details.get("direction") or momentum_details.get("direction") or decision_details.get("final_direction", "no_trade"),
                    "body_ratio": round(body_ratio, 6),
                    "volume_ratio": round(volume_ratio, 6),
                    "rsi": round(rsi, 6),
                    "principal_rejection_reason": principal_reason,
                    "total_score": decision_details.get("total_score"),
                    "setup_detected": gate_details.get("setup_detected"),
                    "condition_failed": gate_details.get("condition_failed"),
                    "value": gate_details.get("value"),
                    "required": gate_details.get("required"),
                    "reason_final": gate_details.get("reason_final"),
                }
            )
    return sorted(candidates, key=lambda item: float(item.get("total_score") or 0.0), reverse=True)[:limit]


def build_valid_dry_run_signals(by_symbol: dict[str, dict[str, dict[str, object]]], *, limit: int) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    for symbol, modules in by_symbol.items():
        decision_engine = modules.get("decision_engine", {})
        signal_builder = modules.get("signal_builder", {})
        momentum = modules.get("momentum", {})
        decision_details = decision_engine.get("details", {}) if isinstance(decision_engine.get("details"), dict) else {}
        signal_details = signal_builder.get("details", {}) if isinstance(signal_builder.get("details"), dict) else {}
        momentum_details = momentum.get("details", {}) if isinstance(momentum.get("details"), dict) else {}
        if decision_details.get("decision") == "SEND" or signal_builder.get("ok") is True:
            signals.append(
                {
                    "symbol": symbol,
                    "direction": signal_details.get("direction", decision_details.get("final_direction", "no_trade")),
                    "setup_type": signal_details.get("setup_type", "UNKNOWN"),
                    "body_ratio": momentum_details.get("body_ratio"),
                    "volume_ratio": momentum_details.get("volume_ratio"),
                    "rsi": momentum_details.get("rsi"),
                    "total_score": decision_details.get("total_score"),
                }
            )
    return sorted(signals, key=lambda item: float(item.get("total_score") or 0.0), reverse=True)[:limit]


def format_summary(summary: dict[str, object]) -> str:
    lines = [
        "Resumen de module_diagnostic",
        f"Total eventos: {summary.get('total_module_diagnostics', 0)}",
        "",
        "Por módulo:",
    ]
    modules = summary.get("modules", [])
    if isinstance(modules, list) and modules:
        for item in modules:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('module')}: ok={item.get('ok_true', 0)} | "
                f"fail={item.get('ok_false', 0)} | score_medio={item.get('average_score', 0)}"
            )
            lines.append(f"  reasons: {_format_reason_list(item.get('top_reasons', []))}")
            lines.append(f"  símbolos: {_format_symbol_list(item.get('top_symbols', []))}")
    else:
        lines.append("- Sin eventos module_diagnostic")

    lines.extend(["", "Top rejection_reasons del decision_engine paralelo:"])
    rejections = summary.get("decision_engine_top_rejection_reasons", [])
    if isinstance(rejections, list) and rejections:
        for item in rejections:
            if isinstance(item, dict):
                lines.append(f"- {item.get('reason', 'unknown')}: {item.get('count', 0)}")
    else:
        lines.append("- Sin rechazos del decision_engine")

    lines.extend(["", "near_miss_candidates:"])
    near_misses = summary.get("near_miss_candidates", [])
    if isinstance(near_misses, list) and near_misses:
        for item in near_misses:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('symbol')} {item.get('direction')}: body={item.get('body_ratio')} | "
                    f"vol={item.get('volume_ratio')} | rsi={item.get('rsi')} | "
                    f"score={item.get('total_score')} | setup={item.get('setup_detected')} | "
                    f"failed={item.get('condition_failed')} value={item.get('value')} required={item.get('required')} | "
                    f"reason={item.get('reason_final') or item.get('principal_rejection_reason')}"
                )
    else:
        lines.append("- Sin near miss candidates")

    lines.extend(["", "valid_dry_run_signals:"])
    valid_signals = summary.get("valid_dry_run_signals", [])
    if isinstance(valid_signals, list) and valid_signals:
        for item in valid_signals:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('symbol')} {item.get('direction')}: setup={item.get('setup_type')} | "
                    f"body={item.get('body_ratio')} | vol={item.get('volume_ratio')} | "
                    f"rsi={item.get('rsi')} | score={item.get('total_score')}"
                )
    else:
        lines.append("- Sin señales válidas detectadas")

    lines.extend(["", "experimental_signals:"])
    experimental = summary.get("experimental_signals", [])
    if isinstance(experimental, list) and experimental:
        for item in experimental:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('symbol')} {item.get('direction')}: score={item.get('score')} | "
                    f"original_block={item.get('original_blocking_filter')} | reason={item.get('experimental_reason')}"
                )
    else:
        lines.append("- Sin señales experimentales")

    comparison = summary.get("signal_decision_comparison", {})
    if not isinstance(comparison, dict):
        comparison = {}
    lines.extend(["", "signal_decision_comparison:"])
    lines.append(f"- coinciden: {comparison.get('matches', 0)}")
    lines.append(f"- difieren: {comparison.get('differs', 0)}")
    current_reject = comparison.get("current_reject_parallel_send_or_paper", [])
    lines.append("- current=REJECT y parallel=SEND/PAPER_ONLY:")
    if isinstance(current_reject, list) and current_reject:
        for item in current_reject:
            if isinstance(item, dict):
                lines.append(
                    f"  - {item.get('symbol')}: current={item.get('current_decision')} "
                    f"parallel={item.get('parallel_decision')} direction={item.get('parallel_direction')} "
                    f"score={item.get('parallel_score')}"
                )
    else:
        lines.append("  - sin casos")
    current_send = comparison.get("current_send_parallel_reject", [])
    lines.append("- current=SEND y parallel=REJECT:")
    if isinstance(current_send, list) and current_send:
        for item in current_send:
            if isinstance(item, dict):
                lines.append(
                    f"  - {item.get('symbol')}: current={item.get('current_decision')} "
                    f"parallel={item.get('parallel_decision')} direction={item.get('current_direction')} "
                    f"score={item.get('current_score')}"
                )
    else:
        lines.append("  - sin casos")
    return "\n".join(lines)


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_reason_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "sin datos"
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.append(f"{item.get('reason')} ({item.get('count')})")
    return ", ".join(parts) if parts else "sin datos"


def _format_symbol_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "sin datos"
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.append(f"{item.get('symbol')} ({item.get('count')})")
    return ", ".join(parts) if parts else "sin datos"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="module-diagnostics-summary")
    parser.add_argument("--log-file", default="logs/scheduler.log")
    parser.add_argument("--stdin", action="store_true", help="Leer logs desde stdin en vez de --log-file")
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = load_module_diagnostics(None if args.stdin else Path(args.log_file))
    print(format_summary(build_summary(rows, limit=args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
