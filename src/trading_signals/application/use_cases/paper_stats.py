from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from trading_signals.data.canonical_trade_source import TradeUniverse, load_trade_universe


CLOSED_STATUSES = {"tp2_hit", "sl_hit", "expired", "tp_hit"}
WIN_STATUSES = {"tp2_hit", "tp_hit"}
LOSS_STATUSES = {"sl_hit"}


def load_paper_trades(data_path: Path) -> list[dict[str, str]]:
    return load_trade_universe(data_path, TradeUniverse.ACCEPTED, closed_only=False)  # type: ignore[return-value]


def build_paper_performance_summary(data_path: Path) -> dict[str, object]:
    trades = load_paper_trades(data_path)
    closed = [trade for trade in trades if _is_closed(trade)]
    total_r = round(sum(_float(trade.get("result_r")) for trade in closed), 4)
    total_closed = len(closed)
    return {
        "trades_total": len(trades),
        "closed_trades": total_closed,
        "open_trades": len([trade for trade in trades if str(trade.get("status", "")) in {"open", "tp1_hit"}]),
        "wins": len([trade for trade in closed if _is_win(trade)]),
        "losses": len([trade for trade in closed if _is_loss(trade)]),
        "expired": len([trade for trade in closed if str(trade.get("status", "")) == "expired"]),
        "winrate": _winrate(closed),
        "total_r": total_r,
        "avg_r": round(total_r / total_closed, 4) if total_closed else 0.0,
        "profit_factor": _profit_factor(closed),
        "best_symbols": _rank_groups(closed, "symbol", reverse=True),
        "worst_symbols": _rank_groups(closed, "symbol", reverse=False),
        "by_setup_type": _group_stats(closed, "setup_type"),
        "by_paper_level": _group_stats(closed, "paper_level"),
        "by_session": _group_stats(closed, "session"),
        "by_opened_hour_utc": _group_stats(closed, "opened_hour_utc"),
        "best_setup_types": _rank_groups(closed, "setup_type", reverse=True),
        "worst_setup_types": _rank_groups(closed, "setup_type", reverse=False),
        "best_paper_levels": _rank_groups(closed, "paper_level", reverse=True),
        "worst_paper_levels": _rank_groups(closed, "paper_level", reverse=False),
        "best_sessions": _rank_groups(closed, "session", reverse=True),
        "worst_sessions": _rank_groups(closed, "session", reverse=False),
        "best_hours": _rank_groups(closed, "opened_hour_utc", reverse=True),
        "worst_hours": _rank_groups(closed, "opened_hour_utc", reverse=False),
        "by_direction": _group_stats(closed, "direction"),
        "top_rejection_reasons": _top_tokens(closed, "entry_or_rejection_reason"),
        "top_failed_conditions": _top_json_list_values(closed, "conditions_failed"),
        "top_avoidance_warnings": _top_json_list_values(closed, "avoidance_warnings"),
        "filter_impact": _filter_impact(closed),
        "latest_10_closed": _latest_closed(closed, limit=10),
        "recommendation": _build_recommendation(closed),
    }


def format_paper_performance_summary(summary: dict[str, object]) -> str:
    return (
        "Resumen rendimiento paper trading\n"
        f"Trades totales: {summary.get('trades_total', 0)}\n"
        f"Cerrados: {summary.get('closed_trades', 0)} | Abiertos: {summary.get('open_trades', 0)}\n"
        f"Ganadas: {summary.get('wins', 0)} | Perdidas: {summary.get('losses', 0)} | Expired: {summary.get('expired', 0)}\n"
        f"Winrate: {summary.get('winrate', 0)}%\n"
        f"PnL/R total: {summary.get('total_r', 0)}R\n"
        f"Media R/trade: {summary.get('avg_r', 0)}R\n"
        f"Profit factor: {summary.get('profit_factor', 0)}\n\n"
        "Mejores símbolos:\n"
        f"{_format_rank(summary.get('best_symbols', []))}\n\n"
        "Peores símbolos:\n"
        f"{_format_rank(summary.get('worst_symbols', []))}\n\n"
        "Mejores sesiones:\n"
        f"{_format_rank(summary.get('best_sessions', []))}\n\n"
        "Peores sesiones:\n"
        f"{_format_rank(summary.get('worst_sessions', []))}\n\n"
        "Mejores horas UTC:\n"
        f"{_format_rank(summary.get('best_hours', []))}\n\n"
        "Peores horas UTC:\n"
        f"{_format_rank(summary.get('worst_hours', []))}\n\n"
        "Rendimiento por dirección:\n"
        f"{_format_group_stats(summary.get('by_direction', {}))}\n\n"
        "Rendimiento por setup_type:\n"
        f"{_format_group_stats(summary.get('by_setup_type', {}))}\n\n"
        "Rendimiento por paper_level:\n"
        f"{_format_group_stats(summary.get('by_paper_level', {}))}\n\n"
        "Rendimiento por session:\n"
        f"{_format_group_stats(summary.get('by_session', {}))}\n\n"
        "Rendimiento por opened_hour_utc:\n"
        f"{_format_group_stats(summary.get('by_opened_hour_utc', {}))}\n\n"
        "Motivos/rechazos frecuentes:\n"
        f"{_format_counter(summary.get('top_rejection_reasons', []))}\n\n"
        "Condiciones fallidas frecuentes:\n"
        f"{_format_counter(summary.get('top_failed_conditions', []))}\n\n"
        "Warnings frecuentes:\n"
        f"{_format_counter(summary.get('top_avoidance_warnings', []))}\n\n"
        "Impacto de filtros/penalizaciones:\n"
        f"{_format_filter_impact(summary.get('filter_impact', {}))}\n\n"
        "Últimas 10 operaciones cerradas:\n"
        f"{_format_latest(summary.get('latest_10_closed', []))}\n\n"
        "Recomendación automática:\n"
        f"{_format_recommendation(summary.get('recommendation', {}))}"
    )


def format_paper_performance_summary_for_telegram(summary: dict[str, object]) -> str:
    return (
        "📊 Paper Trading Summary\n\n"
        f"Trades cerrados: {summary.get('closed_trades', 0)}\n"
        f"Winrate: {summary.get('winrate', 0)}%\n"
        f"Total R: {summary.get('total_r', 0)}R\n"
        f"Avg R/trade: {summary.get('avg_r', 0)}R\n"
        f"Profit factor: {summary.get('profit_factor', 0)}\n\n"
        "LONG vs SHORT\n"
        f"{_format_direction_for_telegram(summary.get('by_direction', {}))}\n\n"
        "Mejores símbolos\n"
        f"{_format_rank_for_telegram(summary.get('best_symbols', []))}\n\n"
        "Peores símbolos\n"
        f"{_format_rank_for_telegram(summary.get('worst_symbols', []))}\n\n"
        "Setup / Nivel\n"
        f"- Mejor setup: {_first_label(summary.get('best_setup_types', []))}\n"
        f"- Peor setup: {_first_label(summary.get('worst_setup_types', []))}\n"
        f"- Mejor nivel: {_first_label(summary.get('best_paper_levels', []))}\n"
        f"- Peor nivel: {_first_label(summary.get('worst_paper_levels', []))}\n\n"
        "Recomendación\n"
        f"{_format_recommendation(summary.get('recommendation', {}))}"
    )


def send_paper_performance_summary(notifier, data_path: Path, *, dry_run: bool = False) -> list[dict[str, object]]:
    summary = build_paper_performance_summary(data_path)
    message = format_paper_performance_summary_for_telegram(summary)
    return notifier.publish(message, dry_run=dry_run)


def _is_closed(trade: dict[str, str]) -> bool:
    return str(trade.get("status", "")) in CLOSED_STATUSES or bool(str(trade.get("closed_at", "")).strip())


def _is_win(trade: dict[str, str]) -> bool:
    return str(trade.get("status", "")) in WIN_STATUSES or _float(trade.get("result_r")) > 0


def _is_loss(trade: dict[str, str]) -> bool:
    return str(trade.get("status", "")) in LOSS_STATUSES or _float(trade.get("result_r")) < 0


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _winrate(closed: list[dict[str, str]]) -> float:
    if not closed:
        return 0.0
    wins = len([trade for trade in closed if _is_win(trade)])
    return round(wins / len(closed) * 100, 2)


def _profit_factor(closed: list[dict[str, str]]) -> float:
    gross_win = sum(max(0.0, _float(trade.get("result_r"))) for trade in closed)
    gross_loss = abs(sum(min(0.0, _float(trade.get("result_r"))) for trade in closed))
    if gross_loss == 0:
        return round(gross_win, 4) if gross_win > 0 else 0.0
    return round(gross_win / gross_loss, 4)


def _group_stats(trades: list[dict[str, str]], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        groups[str(trade.get(key) or "UNKNOWN")].append(trade)
    output: dict[str, dict[str, float | int]] = {}
    for label, items in groups.items():
        total_r = sum(_float(item.get("result_r")) for item in items)
        output[label] = {
            "trades": len(items),
            "winrate": _winrate(items),
            "total_r": round(total_r, 4),
            "avg_r": round(total_r / len(items), 4) if items else 0.0,
            "profit_factor": _profit_factor(items),
        }
    return output


def _rank_groups(trades: list[dict[str, str]], key: str, *, reverse: bool, limit: int = 5) -> list[dict[str, object]]:
    stats = _group_stats(trades, key)
    rows = [{"label": label, **values} for label, values in stats.items()]
    rows.sort(key=lambda item: (float(item.get("avg_r", 0.0)), float(item.get("total_r", 0.0))), reverse=reverse)
    return rows[:limit]


def _top_tokens(trades: list[dict[str, str]], key: str, limit: int = 10) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for trade in trades:
        raw = str(trade.get(key) or "")
        for token in raw.split("|"):
            token = token.strip()
            if token:
                counter[token] += 1
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _top_json_list_values(trades: list[dict[str, str]], key: str, limit: int = 10) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for trade in trades:
        raw = trade.get(key) or ""
        values = _parse_json_list(raw)
        for value in values:
            counter[str(value)] += 1
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _parse_json_list(raw: object) -> list[object]:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return [item.strip() for item in str(raw).split("|") if item.strip()]
    return parsed if isinstance(parsed, list) else []


def _latest_closed(closed: list[dict[str, str]], limit: int) -> list[dict[str, object]]:
    rows = sorted(closed, key=lambda trade: str(trade.get("closed_at") or trade.get("updated_at") or ""), reverse=True)
    return [
        {
            "closed_at": trade.get("closed_at", ""),
            "symbol": trade.get("symbol", "UNKNOWN"),
            "direction": trade.get("direction", "UNKNOWN"),
            "setup_type": trade.get("setup_type", "UNKNOWN"),
            "paper_level": trade.get("paper_level", "UNKNOWN"),
            "status": trade.get("status", "UNKNOWN"),
            "result_r": round(_float(trade.get("result_r")), 4),
        }
        for trade in rows[:limit]
    ]


def _filter_impact(closed: list[dict[str, str]]) -> dict[str, object]:
    tokens = sorted({token for trade in closed for token in _trade_filter_tokens(trade)})
    rows = []
    for token in tokens:
        with_filter = [trade for trade in closed if token in _trade_filter_tokens(trade)]
        without_filter = [trade for trade in closed if token not in _trade_filter_tokens(trade)]
        with_stats = _basic_stats(with_filter)
        without_stats = _basic_stats(without_filter)
        delta_avg_r = round(float(with_stats["avg_r"]) - float(without_stats["avg_r"]), 4)
        delta_winrate = round(float(with_stats["winrate"]) - float(without_stats["winrate"]), 2)
        rows.append(
            {
                "filter": token,
                "frequency": len(with_filter),
                "winrate_with": with_stats["winrate"],
                "total_r_with": with_stats["total_r"],
                "avg_r_with": with_stats["avg_r"],
                "winrate_without": without_stats["winrate"],
                "total_r_without": without_stats["total_r"],
                "avg_r_without": without_stats["avg_r"],
                "delta_avg_r": delta_avg_r,
                "delta_winrate": delta_winrate,
                "classification": _classify_filter_impact(len(with_filter), delta_avg_r, delta_winrate),
            }
        )
    return {
        "filters": rows,
        "useful": _rank_filter_rows(rows, "useful"),
        "neutral": _rank_filter_rows(rows, "neutral"),
        "harmful": _rank_filter_rows(rows, "harmful"),
    }


def _trade_filter_tokens(trade: dict[str, str]) -> set[str]:
    tokens: set[str] = set()
    for token in str(trade.get("entry_or_rejection_reason") or "").split("|"):
        if token.strip():
            tokens.add(token.strip())
    tokens.update(str(item) for item in _parse_json_list(trade.get("conditions_failed") or ""))
    tokens.update(str(item) for item in _parse_json_list(trade.get("avoidance_warnings") or ""))
    for reason in _parse_json_list(trade.get("entry_reasons") or ""):
        text = str(reason)
        if "penalties=" in text:
            penalties = text.split("penalties=", 1)[1]
            for item in penalties.split(","):
                name = item.split(":", 1)[0].strip()
                if name and name != "none":
                    tokens.add(name)
    return tokens


def _basic_stats(trades: list[dict[str, str]]) -> dict[str, float | int]:
    total_r = sum(_float(trade.get("result_r")) for trade in trades)
    return {
        "trades": len(trades),
        "winrate": _winrate(trades),
        "total_r": round(total_r, 4),
        "avg_r": round(total_r / len(trades), 4) if trades else 0.0,
    }


def _classify_filter_impact(frequency: int, delta_avg_r: float, delta_winrate: float) -> str:
    if frequency < 3:
        return "neutral"
    if delta_avg_r >= 0.15 and delta_winrate >= 5:
        return "useful"
    if delta_avg_r <= -0.15 and delta_winrate <= -5:
        return "harmful"
    return "neutral"


def _rank_filter_rows(rows: list[dict[str, object]], classification: str) -> list[dict[str, object]]:
    filtered = [row for row in rows if row.get("classification") == classification]
    reverse = classification != "harmful"
    filtered.sort(key=lambda row: (float(row.get("delta_avg_r", 0.0)), int(row.get("frequency", 0))), reverse=reverse)
    return filtered[:10]


def _build_recommendation(closed: list[dict[str, str]]) -> dict[str, list[str] | str]:
    if len(closed) < 10:
        return {
            "sample": "muestra_insuficiente",
            "keep": [],
            "pause": [],
            "shadow_only": ["mantener todo en paper/shadow hasta tener al menos 10 trades cerrados"],
        }
    candidates: dict[str, dict[str, dict[str, float | int]]] = {
        "direction": _group_stats(closed, "direction"),
        "setup_type": _group_stats(closed, "setup_type"),
        "paper_level": _group_stats(closed, "paper_level"),
        "session": _group_stats(closed, "session"),
        "hour": _group_stats(closed, "opened_hour_utc"),
        "symbol": _group_stats(closed, "symbol"),
    }
    keep: list[str] = []
    pause: list[str] = []
    shadow_only: list[str] = []
    for group_name, stats in candidates.items():
        for label, values in stats.items():
            trades = int(values.get("trades", 0))
            avg_r = float(values.get("avg_r", 0.0))
            pf = float(values.get("profit_factor", 0.0))
            winrate = float(values.get("winrate", 0.0))
            item = f"{group_name}:{label} ({trades} trades, WR {winrate}%, PF {pf}, avgR {avg_r})"
            if trades < 3:
                continue
            if avg_r > 0.2 and pf >= 1.2:
                keep.append(item)
            elif avg_r < -0.25 and pf < 0.8:
                pause.append(item)
            elif avg_r < 0.05 or pf < 1.0:
                shadow_only.append(item)
    return {
        "sample": "ok",
        "keep": keep[:8],
        "pause": pause[:8],
        "shadow_only": shadow_only[:8],
    }


def _format_rank(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- Sin datos"
    return "\n".join(
        f"- {item.get('label')}: trades {item.get('trades')} | WR {item.get('winrate')}% | totalR {item.get('total_r')} | avgR {item.get('avg_r')}"
        for item in items
        if isinstance(item, dict)
    )


def _format_group_stats(stats: object) -> str:
    if not isinstance(stats, dict) or not stats:
        return "- Sin datos"
    lines = []
    for label, values in sorted(stats.items()):
        if isinstance(values, dict):
            lines.append(
                f"- {label}: trades {values.get('trades')} | WR {values.get('winrate')}% | "
                f"totalR {values.get('total_r')} | avgR {values.get('avg_r')} | PF {values.get('profit_factor')}"
            )
    return "\n".join(lines) if lines else "- Sin datos"


def _format_counter(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- Sin datos"
    return "\n".join(f"- {item.get('label')}: {item.get('count')}" for item in items if isinstance(item, dict))


def _format_latest(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- Sin operaciones cerradas"
    lines = []
    for item in items:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('closed_at')}: {item.get('symbol')} {str(item.get('direction')).upper()} "
                f"{item.get('status')} {item.get('result_r')}R"
            )
    return "\n".join(lines) if lines else "- Sin operaciones cerradas"


def _format_recommendation(recommendation: object) -> str:
    if not isinstance(recommendation, dict) or not recommendation:
        return "- Sin datos"
    if recommendation.get("sample") == "muestra_insuficiente":
        return "- Muestra insuficiente: mantener en paper/shadow"
    lines = []
    for title, key in (("Mantener", "keep"), ("Pausar", "pause"), ("Solo shadow/paper", "shadow_only")):
        values = recommendation.get(key, [])
        if isinstance(values, list) and values:
            lines.append(f"{title}:")
            lines.extend(f"- {value}" for value in values[:5])
        else:
            lines.append(f"{title}: sin candidatos claros")
    return "\n".join(lines)


def _format_filter_impact(impact: object) -> str:
    if not isinstance(impact, dict) or not impact:
        return "- Sin datos"
    sections = []
    for title, key in (("Filtros útiles", "useful"), ("Filtros neutros", "neutral"), ("Filtros perjudiciales", "harmful")):
        rows = impact.get(key, [])
        sections.append(f"{title}:")
        if not isinstance(rows, list) or not rows:
            sections.append("- Sin candidatos")
            continue
        for row in rows[:5]:
            if isinstance(row, dict):
                sections.append(
                    f"- {row.get('filter')}: freq {row.get('frequency')} | WR {row.get('winrate_with')}% "
                    f"vs {row.get('winrate_without')}% | totalR {row.get('total_r_with')} | "
                    f"avgR {row.get('avg_r_with')} vs {row.get('avg_r_without')} | ΔavgR {row.get('delta_avg_r')}"
                )
    return "\n".join(sections)


def _format_direction_for_telegram(stats: object) -> str:
    if not isinstance(stats, dict) or not stats:
        return "- Sin datos"
    lines = []
    for direction in ("long", "short"):
        values = stats.get(direction)
        if isinstance(values, dict):
            lines.append(
                f"- {direction.upper()}: trades {values.get('trades', 0)} | WR {values.get('winrate', 0)}% | "
                f"R {values.get('total_r', 0)} | avgR {values.get('avg_r', 0)}"
            )
    return "\n".join(lines) if lines else "- Sin datos"


def _format_rank_for_telegram(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- Sin datos"
    lines = []
    for item in items[:3]:
        if isinstance(item, dict):
            lines.append(f"- {item.get('label')}: R {item.get('total_r')} | avgR {item.get('avg_r')} | WR {item.get('winrate')}%")
    return "\n".join(lines) if lines else "- Sin datos"


def _first_label(items: object) -> str:
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return str(items[0].get("label", "sin_datos"))
    return "sin_datos"
