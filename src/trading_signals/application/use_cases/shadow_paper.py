from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.application.use_cases.experimental_paper import (
    candles_after_timestamp,
    evaluate_experimental_outcome,
    mature_winrate,
    prices_are_similar,
    winrate,
)


SHADOW_SIGNAL_FIELDS = [
    "timestamp",
    "symbol",
    "direction",
    "entry_price",
    "shadow_decision",
    "shadow_score",
    "current_decision",
    "current_rejection_reasons",
    "module_scores",
    "trend_ok",
    "momentum_ok",
    "liquidity_ok",
    "market_regime",
    "rsi",
    "body_ratio",
    "volume_ratio",
    "outcome",
    "max_favorable_move",
    "max_adverse_move",
    "candles_elapsed",
    "exit_reason",
    "evaluated_at",
]


class ShadowSignalStore:
    def __init__(self, base_path: Path, *, price_tolerance_pct: float = 0.001) -> None:
        self.signals_file = base_path / "paper_trading" / "shadow_signals.csv"
        self.price_tolerance_pct = price_tolerance_pct
        self.duplicate_skipped_count = 0

    def list_signals(self) -> list[dict[str, str]]:
        if not self.signals_file.exists():
            return []
        with self.signals_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_signals(self, rows: list[dict[str, object]]) -> None:
        self.signals_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.signals_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=SHADOW_SIGNAL_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in SHADOW_SIGNAL_FIELDS})
        temp.replace(self.signals_file)

    def upsert_signal(self, row: dict[str, object]) -> bool:
        rows: list[dict[str, object]] = list(self.list_signals())
        if any(self._is_duplicate(existing, row) for existing in rows):
            self.duplicate_skipped_count += 1
            return False
        rows.append(
            {
                **row,
                "outcome": "pending",
                "max_favorable_move": "0",
                "max_adverse_move": "0",
                "candles_elapsed": "0",
                "exit_reason": "",
                "evaluated_at": "",
            }
        )
        self.save_signals(rows)
        return True

    def update_pending_outcomes(
        self,
        market_data,
        *,
        interval: str = "1h",
        win_threshold: float = 0.015,
        loss_threshold: float = 0.01,
        limit: int = 300,
        evaluated_at: str | None = None,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = list(self.list_signals())
        updated: list[dict[str, object]] = []
        evaluated_at = evaluated_at or datetime.now(tz=UTC).isoformat()
        for row in rows:
            if row.get("outcome") != "pending":
                continue
            candles = market_data.fetch_ohlcv(str(row.get("symbol")), interval, limit=limit)
            later_candles = candles_after_timestamp(candles, str(row.get("timestamp", "")))
            result = evaluate_experimental_outcome(
                row,
                later_candles,
                win_threshold=win_threshold,
                loss_threshold=loss_threshold,
            )
            row.update(result)
            row["evaluated_at"] = evaluated_at
            updated.append(dict(row))
        if updated:
            self.save_signals(rows)
        return updated

    def build_summary(self) -> dict[str, object]:
        rows = self.list_signals()
        closed = [row for row in rows if row.get("outcome") in {"win", "loss"}]
        return {
            "shadow_detected": len(rows),
            "wins": len([row for row in rows if row.get("outcome") == "win"]),
            "losses": len([row for row in rows if row.get("outcome") == "loss"]),
            "pending": len([row for row in rows if row.get("outcome") == "pending"]),
            "winrate": winrate(closed),
            "winrate_candles_5": mature_winrate(rows, min_candles=5),
            "winrate_candles_10": mature_winrate(rows, min_candles=10),
            "by_direction": dict(Counter(row.get("direction", "unknown") for row in rows)),
            "by_shadow_decision": dict(Counter(row.get("shadow_decision", "unknown") for row in rows)),
            "by_market_regime": dict(Counter(row.get("market_regime", "unknown") for row in rows)),
            "by_score": dict(Counter(shadow_score_bucket(float(row.get("shadow_score") or 0.0)) for row in rows)),
        }

    def _is_duplicate(self, existing: dict[str, object], candidate: dict[str, object]) -> bool:
        if str(existing.get("outcome", "pending")) != "pending":
            return False
        if str(existing.get("symbol")) != str(candidate.get("symbol")):
            return False
        if str(existing.get("direction")) != str(candidate.get("direction")):
            return False
        if str(existing.get("shadow_decision")) != str(candidate.get("shadow_decision")):
            return False
        return prices_are_similar(
            float(existing.get("entry_price") or 0.0),
            float(candidate.get("entry_price") or 0.0),
            tolerance_pct=self.price_tolerance_pct,
        )


def build_shadow_signal_row(
    *,
    timestamp: str,
    symbol: str,
    snapshot,
    current_decision,
    module_diagnostics: dict[str, dict[str, object]],
) -> dict[str, object] | None:
    decision_engine = module_diagnostics.get("decision_engine", {})
    details = decision_engine.get("details", {}) if isinstance(decision_engine.get("details"), dict) else {}
    shadow_decision = str(details.get("shadow_decision", "REJECT"))
    if shadow_decision not in {"SEND", "PAPER_ONLY"}:
        return None
    momentum = module_diagnostics.get("momentum", {})
    momentum_details = momentum.get("details", {}) if isinstance(momentum.get("details"), dict) else {}
    market_regime = module_diagnostics.get("market_regime", {})
    market_details = market_regime.get("details", {}) if isinstance(market_regime.get("details"), dict) else {}
    module_scores = {
        name: result.get("score", 0.0)
        for name, result in module_diagnostics.items()
        if name in {"trend", "momentum", "liquidity", "market_regime", "risk"}
    }
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": details.get("shadow_direction", "no_trade"),
        "entry_price": snapshot.close,
        "shadow_decision": shadow_decision,
        "shadow_score": details.get("shadow_score", 0.0),
        "current_decision": current_decision.decision,
        "current_rejection_reasons": json.dumps(current_decision.rejection_reasons, ensure_ascii=False),
        "module_scores": json.dumps(module_scores, ensure_ascii=False, sort_keys=True),
        "trend_ok": bool(module_diagnostics.get("trend", {}).get("ok")),
        "momentum_ok": bool(momentum.get("ok")),
        "liquidity_ok": bool(module_diagnostics.get("liquidity", {}).get("ok")),
        "market_regime": market_details.get("market_regime"),
        "rsi": momentum_details.get("rsi"),
        "body_ratio": momentum_details.get("body_ratio"),
        "volume_ratio": momentum_details.get("volume_ratio"),
    }


def format_shadow_summary(summary: dict[str, object]) -> str:
    return (
        "Resumen shadow signals\n"
        f"Detectadas: {summary.get('shadow_detected', 0)}\n"
        f"Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)} | Pending: {summary.get('pending', 0)}\n"
        f"Winrate provisional: {summary.get('winrate', 0)}%\n"
        f"Winrate candles>=5: {summary.get('winrate_candles_5', {}).get('winrate', 0)}% "
        f"({summary.get('winrate_candles_5', {}).get('closed', 0)} cerradas / {summary.get('winrate_candles_5', {}).get('eligible', 0)} elegibles)\n"
        f"Winrate candles>=10: {summary.get('winrate_candles_10', {}).get('winrate', 0)}% "
        f"({summary.get('winrate_candles_10', {}).get('closed', 0)} cerradas / {summary.get('winrate_candles_10', {}).get('eligible', 0)} elegibles)\n"
        f"Por dirección: {summary.get('by_direction', {})}\n"
        f"Por shadow_decision: {summary.get('by_shadow_decision', {})}\n"
        f"Por market_regime: {summary.get('by_market_regime', {})}\n"
        f"Por score: {summary.get('by_score', {})}"
    )


def shadow_score_bucket(score: float) -> str:
    if score >= 90:
        return "90+"
    if score >= 80:
        return "80-89"
    if score >= 65:
        return "65-79"
    return "<65"
