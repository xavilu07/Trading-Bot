from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe el fichero de diagnóstico: {csv_path}")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    rejection_reason_counter: Counter[str] = Counter()
    filter_counter: Counter[str] = Counter()
    symbol_counter: Counter[str] = Counter()

    for row in rows:
        symbol = row.get("symbol", "").strip()
        rejection_reason = row.get("rejection_reason", "").strip()
        if symbol:
            symbol_counter[symbol] += 1
        if rejection_reason:
            rejection_reason_counter[rejection_reason] += 1
            for reason in rejection_reason.split("|"):
                clean_reason = reason.strip()
                if clean_reason:
                    filter_counter[clean_reason] += 1

    total_no_trade = len(rows)
    recommendations: list[str] = []

    def maybe_recommend(filter_name: str, recommendation: str) -> None:
        if total_no_trade == 0:
            return
        if filter_counter[filter_name] / total_no_trade > 0.5:
            recommendations.append(recommendation)

    maybe_recommend(
        "body_ratio_below_threshold",
        "Sugerencia: `body_ratio_below_threshold` supera el 50%. Revisar una bajada de `MIN_BODY_RATIO`.",
    )
    maybe_recommend(
        "quality_score_failed",
        "Sugerencia: `quality_score_failed` supera el 50%. Revisar `SETUP_SCORE_THRESHOLD`.",
    )
    maybe_recommend(
        "market_structure_range",
        "Sugerencia: `market_structure_range` supera el 50%. Revisar o relajar el detector de estructura.",
    )
    maybe_recommend(
        "distance_to_liquidity_failed",
        "Sugerencia: `distance_to_liquidity_failed` supera el 50%. Revisar ampliar la distancia máxima a liquidez.",
    )

    return {
        "total_symbols_analyzed": total_no_trade,
        "total_no_trade": total_no_trade,
        "rejection_reason_ranking": rejection_reason_counter.most_common(),
        "filter_counts": filter_counter.most_common(),
        "blocked_symbols": symbol_counter.most_common(),
        "recommendations": recommendations,
    }


def format_summary(summary: dict[str, object], csv_path: Path) -> str:
    lines = [
        f"Resumen diario de diagnósticos: {csv_path}",
        f"1. Total de símbolos analizados: {summary['total_symbols_analyzed']}",
        f"2. Total de NO_TRADE: {summary['total_no_trade']}",
        "3. Ranking de rejection_reason más frecuentes:",
    ]

    for reason, count in summary["rejection_reason_ranking"]:
        lines.append(f"   - {reason}: {count}")
    if not summary["rejection_reason_ranking"]:
        lines.append("   - Sin datos")

    lines.append("4. Conteo individual por filtro:")
    for reason, count in summary["filter_counts"]:
        lines.append(f"   - {reason}: {count}")
    if not summary["filter_counts"]:
        lines.append("   - Sin datos")

    lines.append("5. Símbolos más bloqueados:")
    for symbol, count in summary["blocked_symbols"]:
        lines.append(f"   - {symbol}: {count}")
    if not summary["blocked_symbols"]:
        lines.append("   - Sin datos")

    lines.append("6. Recomendación automática:")
    for recommendation in summary["recommendations"]:
        lines.append(f"   - {recommendation}")
    if not summary["recommendations"]:
        lines.append("   - No hay recomendaciones automáticas para hoy.")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="diagnostics-summary")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--base-path", default="data/diagnostics/no_trade_diagnostics")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    csv_path = Path(args.base_path) / f"{args.date}.csv"
    rows = load_rows(csv_path)
    summary = build_summary(rows)
    print(format_summary(summary, csv_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
